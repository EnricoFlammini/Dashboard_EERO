import asyncio
import logging
from datetime import datetime, timezone, time as dt_time
from typing import Any, Dict, List, Optional, Set

from app.config import settings
from app.services.adguard import adguard_service
from app.services.db import db_service
from app.services.eero_client import eero_client
from app.services.notifications import notification_service
from app.services.speedtest_service import speedtest_service

logger = logging.getLogger(__name__)


class BackgroundPoller:
    """
    Background worker that periodically polls eero cloud/local state,
    maintains an in-memory RAM cache for instant 0ms UI delivery,
    records historical metrics into SQLite, and triggers alerts/automations.
    """

    def __init__(self):
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._last_poll_time: Optional[datetime] = None
        
        # In-Memory Cache
        self.cached_network: Dict[str, Any] = {}
        self.cached_eeros: List[Dict[str, Any]] = []
        self.cached_devices: List[Dict[str, Any]] = []
        self.cached_profiles: List[Dict[str, Any]] = []
        self.cached_health_score: int = 100
        self.cached_health_details: Dict[str, Any] = {}
        
        # Tracking states for alert detection
        self._known_macs: Set[str] = set()
        self._initial_macs_loaded: bool = False
        self._known_eeros_status: Dict[str, str] = {}
        self._last_night_mode_state: Optional[bool] = None
        self._last_retention_run: Optional[datetime] = None
        self._last_scheduled_speedtest: Optional[datetime] = None
        self._last_digest_date: Optional[str] = None
        self._last_adguard_sync: Optional[datetime] = None
        self._prev_device_metrics: Dict[str, Dict[str, Any]] = {}
        self._prev_poll_time: Optional[datetime] = None

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"Background Poller started (Interval: {settings.poll_interval}s).")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Background Poller stopped.")

    def get_cached_state(self) -> Dict[str, Any]:
        """Restituisce istantaneamente lo stato in RAM con latenza zero."""
        return {
            "network": self.cached_network,
            "eeros": self.cached_eeros,
            "devices": self.cached_devices,
            "profiles": self.cached_profiles,
            "health_score": self.cached_health_score,
            "health_details": self.cached_health_details,
            "last_poll_time": self._last_poll_time.isoformat() if self._last_poll_time else None,
            "is_authenticated": eero_client.is_authenticated,
            "demo_mode": settings.demo_mode or (eero_client.user_token and eero_client.user_token.startswith("demo_")),
        }

    async def poll_once(self):
        """Esegue un ciclo di polling immediato e aggiorna la cache."""
        await self._poll_and_cache()

    def calculate_health_details(
        self,
        network_details: Dict[str, Any],
        eeros: List[Dict[str, Any]],
        enriched_devices: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calcola la diagnostica a 4 pilastri, penalità attive e raccomandazioni (Issue #15)."""
        penalties = []
        recommendations = []
        recommendations_i18n = []

        # 1. Mesh Topology & Nodes (Max 40 pt)
        mesh_max = 40
        mesh_score = mesh_max
        mesh_issues = []
        mesh_issues_en = []

        offline_nodes = [e for e in eeros if e.get("status") not in ("online", "green")]
        if offline_nodes:
            deduction = len(offline_nodes) * 20
            mesh_score = max(0, mesh_score - deduction)
            names = [e.get("name") or e.get("location") or "Nodo eero" for e in offline_nodes]
            names_en = [e.get("name") or e.get("location") or "eero node" for e in offline_nodes]
            mesh_issues.append(f"{len(offline_nodes)} nodi offline: {', '.join(names)}")
            mesh_issues_en.append(f"{len(offline_nodes)} offline node(s): {', '.join(names_en)}")
            penalties.append({
                "id": "offline_nodes",
                "pillar": "mesh_topology",
                "title": "Nodi Mesh Disconnessi",
                "title_i18n": {
                    "it": "Nodi Mesh Disconnessi",
                    "en": "Disconnected Mesh Nodes"
                },
                "impact": -min(deduction, mesh_max),
                "severity": "critical",
                "description": f"{len(offline_nodes)} nodo/i eero risultano offline o non raggiungibili.",
                "description_i18n": {
                    "it": f"{len(offline_nodes)} nodo/i eero risultano offline o non raggiungibili.",
                    "en": f"{len(offline_nodes)} eero node(s) are offline or unreachable."
                },
                "affected_items": names
            })
            recommendations.append(f"Verifica l'alimentazione e la connettività dei nodi disconnessi ({', '.join(names)}).")
            recommendations_i18n.append({
                "it": f"Verifica l'alimentazione e la connettività dei nodi disconnessi ({', '.join(names)}).",
                "en": f"Check power and connectivity for disconnected nodes ({', '.join(names)})."
            })

        # Verifica degradamento backhaul su nodi wireless o cablati
        degraded_backhaul_nodes = []
        degraded_backhaul_nodes_en = []
        for e in eeros:
            if e.get("status") in ("online", "green") and not e.get("is_gateway"):
                rssi = e.get("signal_rssi")
                if isinstance(rssi, (int, float)) and rssi < -75:
                    degraded_backhaul_nodes.append(f"{e.get('name')} (Backhaul debole: {rssi} dBm)")
                    degraded_backhaul_nodes_en.append(f"{e.get('name')} (Weak backhaul: {rssi} dBm)")
                backhaul_str = str(e.get("backhaul_type") or "").lower()
                if "100 mbps" in backhaul_str or "100m" in backhaul_str:
                    degraded_backhaul_nodes.append(f"{e.get('name')} (Cavo limitato a 100 Mbps)")
                    degraded_backhaul_nodes_en.append(f"{e.get('name')} (Cable limited to 100 Mbps)")

        if degraded_backhaul_nodes and mesh_score > 5:
            backhaul_deduction = min(len(degraded_backhaul_nodes) * 5, 10)
            mesh_score = max(0, mesh_score - backhaul_deduction)
            mesh_issues.append(f"Backhaul degradato su {len(degraded_backhaul_nodes)} nodi")
            mesh_issues_en.append(f"Degraded backhaul on {len(degraded_backhaul_nodes)} node(s)")
            penalties.append({
                "id": "degraded_backhaul",
                "pillar": "mesh_topology",
                "title": "Collegamento Backhaul Degradato",
                "title_i18n": {
                    "it": "Collegamento Backhaul Degradato",
                    "en": "Degraded Backhaul Link"
                },
                "impact": -backhaul_deduction,
                "severity": "warning",
                "description": "Alcuni nodi estensori presentano un collegamento backhaul debole o limitato a 100 Mbps.",
                "description_i18n": {
                    "it": "Alcuni nodi estensori presentano un collegamento backhaul debole o limitato a 100 Mbps.",
                    "en": "Some mesh extender nodes have weak wireless backhaul or a link limited to 100 Mbps."
                },
                "affected_items": degraded_backhaul_nodes
            })
            recommendations.append("Per i nodi con segnale mesh debole, riduci la distanza dal Gateway. Per i collegamenti cablati a 100 Mbps, verifica l'integrità del cavo Ethernet Cat 5e/6.")
            recommendations_i18n.append({
                "it": "Per i nodi con segnale mesh debole, riduci la distanza dal Gateway. Per i collegamenti cablati a 100 Mbps, verifica l'integrità del cavo Ethernet Cat 5e/6.",
                "en": "For nodes with weak mesh signal, reduce distance to Gateway. For 100 Mbps links, verify Ethernet Cat 5e/6 cable integrity."
            })

        mesh_status = "optimal" if mesh_score >= 35 else ("warning" if mesh_score >= 20 else "critical")
        mesh_details_text = (
            f"{len(eeros) - len(offline_nodes)}/{len(eeros)} nodi operativi con backhaul eccellente."
            if not mesh_issues else "; ".join(mesh_issues)
        )
        mesh_details_text_en = (
            f"{len(eeros) - len(offline_nodes)}/{len(eeros)} operational nodes with excellent backhaul."
            if not mesh_issues_en else "; ".join(mesh_issues_en)
        )

        # 2. WAN & Gateway Connectivity (Max 30 pt)
        wan_max = 30
        wan_score = wan_max
        wan_issues = []
        wan_issues_en = []

        is_wan_online = network_details.get("status") in ("online", "green")
        if not is_wan_online:
            wan_score = 0
            wan_issues.append("Connessione Internet non attiva o gateway offline")
            wan_issues_en.append("Internet connection inactive or gateway offline")
            penalties.append({
                "id": "wan_offline",
                "pillar": "wan_gateway",
                "title": "Internet WAN Non Raggiungibile",
                "title_i18n": {
                    "it": "Internet WAN Non Raggiungibile",
                    "en": "WAN Internet Unreachable"
                },
                "impact": -wan_max,
                "severity": "critical",
                "description": "La rete eero segnala interruzione dell'accesso Internet dal provider o gateway offline.",
                "description_i18n": {
                    "it": "La rete eero segnala interruzione dell'accesso Internet dal provider o gateway offline.",
                    "en": "eero network reports loss of Internet access from provider or gateway offline."
                },
                "affected_items": ["Gateway WAN"]
            })
            recommendations.append("Controlla il cavo tra il modem del provider (ONT/FTTH/DSL) e la porta WAN del gateway eero.")
            recommendations_i18n.append({
                "it": "Controlla il cavo tra il modem del provider (ONT/FTTH/DSL) e la porta WAN del gateway eero.",
                "en": "Check the cable between your provider modem (ONT/FTTH/DSL) and the eero gateway WAN port."
            })
        else:
            sp = network_details.get("speedtest") or {}
            ping_val = float(sp.get("ping_ms") or 0.0)
            if ping_val > 80.0:
                wan_score = max(10, wan_score - 10)
                wan_issues.append(f"Latenza elevata verso gateway/ISP ({ping_val:.1f} ms)")
                wan_issues_en.append(f"High latency to gateway/ISP ({ping_val:.1f} ms)")
                penalties.append({
                    "id": "high_wan_latency",
                    "pillar": "wan_gateway",
                    "title": "Latenza Internet Elevata",
                    "title_i18n": {
                        "it": "Latenza Internet Elevata",
                        "en": "High Internet Latency"
                    },
                    "impact": -10,
                    "severity": "warning",
                    "description": f"Il ping medio registrato dal Gateway verso la rete esterna è elevato ({ping_val:.1f} ms > 80 ms).",
                    "description_i18n": {
                        "it": f"Il ping medio registrato dal Gateway verso la rete esterna è elevato ({ping_val:.1f} ms > 80 ms).",
                        "en": f"Average ping recorded from Gateway to external network is high ({ping_val:.1f} ms > 80 ms)."
                    },
                    "affected_items": [f"Ping Gateway: {ping_val:.1f} ms"]
                })
                recommendations.append("Se la latenza rimane costantemente sopra 80 ms, esegui un test diretto o verifica congestioni sul modem/router del provider.")
                recommendations_i18n.append({
                    "it": "Se la latenza rimane costantemente sopra 80 ms, esegui un test diretto o verifica congestioni sul modem/router del provider.",
                    "en": "If latency remains consistently above 80 ms, run a direct speed test or check provider modem/router congestion."
                })
            elif ping_val > 45.0:
                wan_score = max(20, wan_score - 5)
                wan_issues.append(f"Latenza moderata ({ping_val:.1f} ms)")
                wan_issues_en.append(f"Moderate latency ({ping_val:.1f} ms)")
                penalties.append({
                    "id": "moderate_wan_latency",
                    "pillar": "wan_gateway",
                    "title": "Latenza Internet Moderata",
                    "title_i18n": {
                        "it": "Latenza Internet Moderata",
                        "en": "Moderate Internet Latency"
                    },
                    "impact": -5,
                    "severity": "info",
                    "description": f"Latenza WAN registrata di {ping_val:.1f} ms (sopra la soglia ideale di 45 ms).",
                    "description_i18n": {
                        "it": f"Latenza WAN registrata di {ping_val:.1f} ms (sopra la soglia ideale di 45 ms).",
                        "en": f"Recorded WAN latency of {ping_val:.1f} ms (above ideal 45 ms threshold)."
                    },
                    "affected_items": [f"Ping: {ping_val:.1f} ms"]
                })

        wan_status = "optimal" if wan_score >= 25 else ("warning" if wan_score >= 15 else "critical")
        wan_details_text = (
            f"Gateway online, IP pubblico attivo ({network_details.get('public_ip', 'N/D')}), latenza ottimale."
            if not wan_issues else "; ".join(wan_issues)
        )
        wan_details_text_en = (
            f"Gateway online, active public IP ({network_details.get('public_ip', 'N/A')}), optimal latency."
            if not wan_issues_en else "; ".join(wan_issues_en)
        )

        # 3. Client Wi-Fi Signal Quality (Max 20 pt)
        client_max = 20
        client_score = client_max
        client_issues = []
        client_issues_en = []

        connected_clients = [d for d in enriched_devices if d.get("connected")]
        wireless_connected = [d for d in connected_clients if d.get("wireless")]

        weak_devices = []
        critical_devices = []
        for d in wireless_connected:
            rssi = d.get("signal_rssi")
            if isinstance(rssi, (int, float)):
                d_name = d.get("custom_name") or d.get("nickname") or d.get("hostname") or d.get("mac") or "Dispositivo"
                eero_name = d.get("connected_eero_name") or "eero"
                item_label = f"{d_name} ({rssi} dBm su {eero_name})"
                if rssi < -82:
                    critical_devices.append(item_label)
                elif rssi < -75:
                    weak_devices.append(item_label)

        total_degraded = len(weak_devices) + len(critical_devices)
        if total_degraded > 0:
            deduction = (len(weak_devices) * 2) + (len(critical_devices) * 3)
            deduction = min(deduction, 18)
            client_score = max(2, client_score - deduction)
            all_affected = critical_devices + weak_devices
            client_issues.append(f"{total_degraded} dispositivi con segnale debole")
            client_issues_en.append(f"{total_degraded} device(s) with weak signal")
            penalties.append({
                "id": "weak_client_signal",
                "pillar": "client_signal",
                "title": "Client con Segnale Wi-Fi Degradato",
                "title_i18n": {
                    "it": "Client con Segnale Wi-Fi Degradato",
                    "en": "Clients with Degraded Wi-Fi Signal"
                },
                "impact": -deduction,
                "severity": "warning" if len(critical_devices) == 0 else "critical",
                "description": f"{total_degraded} dispositivi wireless presentano un segnale RSSI degradato (< -75 dBm), che può causare perdita pacchetti o throughput ridotto.",
                "description_i18n": {
                    "it": f"{total_degraded} dispositivi wireless presentano un segnale RSSI degradato (< -75 dBm), che può causare perdita pacchetti o throughput ridotto.",
                    "en": f"{total_degraded} wireless device(s) have degraded RSSI signal (< -75 dBm), which may cause packet loss or reduced throughput."
                },
                "affected_items": all_affected[:6]
            })
            recommendations.append(f"Avvicina i dispositivi ({', '.join(all_affected[:3])}) al nodo mesh più vicino o valuta un riposizionamento per eliminare zone d'ombra.")
            recommendations_i18n.append({
                "it": f"Avvicina i dispositivi ({', '.join(all_affected[:3])}) al nodo mesh più vicino o valuta un riposizionamento per eliminare zone d'ombra.",
                "en": f"Move devices ({', '.join(all_affected[:3])}) closer to the nearest mesh node or consider repositioning to eliminate dead zones."
            })

        client_status = "optimal" if client_score >= 18 else ("warning" if client_score >= 10 else "critical")
        client_details_text = (
            f"Tutti i {len(wireless_connected)} dispositivi wireless hanno segnale RSSI eccellente (>= -75 dBm)."
            if not client_issues else "; ".join(client_issues)
        )
        client_details_text_en = (
            f"All {len(wireless_connected)} wireless devices have excellent RSSI signal (>= -75 dBm)."
            if not client_issues_en else "; ".join(client_issues_en)
        )

        # 4. Channel Distribution & Density (Max 10 pt)
        channel_max = 10
        channel_score = channel_max
        channel_issues = []
        channel_issues_en = []

        c_6g = sum(1 for d in wireless_connected if "6" in str(d.get("wireless_band", "")))
        c_5g = sum(1 for d in wireless_connected if "5" in str(d.get("wireless_band", "")))
        c_24g = sum(1 for d in wireless_connected if "2.4" in str(d.get("wireless_band", "")))
        total_w = len(wireless_connected)

        if total_w >= 6 and (c_24g / total_w) > 0.70 and (c_5g + c_6g) > 0:
            channel_score = max(5, channel_score - 3)
            channel_issues.append("Sovraccarico frequenza 2.4 GHz (> 70% dei client)")
            channel_issues_en.append("2.4 GHz band overload (> 70% of clients)")
            penalties.append({
                "id": "band_24_crowding",
                "pillar": "channel_density",
                "title": "Affollamento Frequenza 2.4 GHz",
                "title_i18n": {
                    "it": "Affollamento Frequenza 2.4 GHz",
                    "en": "2.4 GHz Band Crowding"
                },
                "impact": -3,
                "severity": "info",
                "description": f"{c_24g} su {total_w} client wireless sono connessi sui canali 2.4 GHz, con potenziale saturazione dello spettro.",
                "description_i18n": {
                    "it": f"{c_24g} su {total_w} client wireless sono connessi sui canali 2.4 GHz, con potenziale saturazione dello spettro.",
                    "en": f"{c_24g} out of {total_w} wireless clients are connected on 2.4 GHz channels, potentially saturating the spectrum."
                },
                "affected_items": [f"2.4 GHz: {c_24g} client", f"5 GHz: {c_5g} client", f"6 GHz: {c_6g} client"]
            })
            recommendations.append("Attiva la funzione 'Band Steering' nelle impostazioni per instradare automaticamente i dispositivi compatibili sui 5 GHz o 6 GHz.")
            recommendations_i18n.append({
                "it": "Attiva la funzione 'Band Steering' nelle impostazioni per instradare automaticamente i dispositivi compatibili sui 5 GHz o 6 GHz.",
                "en": "Enable 'Band Steering' in settings to automatically route compatible devices to 5 GHz or 6 GHz."
            })

        if len(eeros) > 1 and total_w >= 8:
            for node in eeros:
                cnt = node.get("connected_clients_count", 0)
                if cnt / len(connected_clients) > 0.80 and cnt >= 15:
                    node_name = node.get("name") or "Nodo"
                    channel_score = max(4, channel_score - 3)
                    channel_issues.append(f"Carico client sbilanciato su {node_name} ({cnt} client)")
                    channel_issues_en.append(f"Unbalanced client load on {node_name} ({cnt} clients)")
                    penalties.append({
                        "id": "node_overload",
                        "pillar": "channel_density",
                        "title": "Sbilanciamento Carico Nodi Mesh",
                        "title_i18n": {
                            "it": "Sbilanciamento Carico Nodi Mesh",
                            "en": "Mesh Node Load Imbalance"
                        },
                        "impact": -3,
                        "severity": "info",
                        "description": f"Il nodo '{node_name}' gestisce oltre l'80% di tutti i dispositivi connessi della casa.",
                        "description_i18n": {
                            "it": f"Il nodo '{node_name}' gestisce oltre l'80% di tutti i dispositivi connessi della casa.",
                            "en": f"Node '{node_name}' handles more than 80% of all connected household devices."
                        },
                        "affected_items": [f"{node_name}: {cnt} client"]
                    })
                    break

        channel_status = "optimal" if channel_score >= 8 else ("warning" if channel_score >= 5 else "critical")
        channel_details_text = (
            f"Distribuzione frequenze bilanciata: 6 GHz ({c_6g}), 5 GHz ({c_5g}), 2.4 GHz ({c_24g})."
            if not channel_issues else "; ".join(channel_issues)
        )
        channel_details_text_en = (
            f"Balanced frequency distribution: 6 GHz ({c_6g}), 5 GHz ({c_5g}), 2.4 GHz ({c_24g})."
            if not channel_issues_en else "; ".join(channel_issues_en)
        )

        # Calcolo Score Finale (1 - 100)
        total_score = mesh_score + wan_score + client_score + channel_score
        final_score = max(5, min(100, total_score))

        overall_status = "optimal" if final_score >= 90 else ("good" if final_score >= 70 else ("warning" if final_score >= 50 else "critical"))

        if not recommendations:
            recommendations.append("Tutti i parametri di stabilità della rete eero mesh sono ottimali. Nessuna azione correttiva necessaria.")
            recommendations_i18n.append({
                "it": "Tutti i parametri di stabilità della rete eero mesh sono ottimali. Nessuna azione correttiva necessaria.",
                "en": "All eero mesh stability parameters are optimal. No corrective action needed."
            })

        return {
            "score": final_score,
            "status": overall_status,
            "penalties": penalties,
            "pillars": {
                "mesh_topology": {
                    "key": "mesh_topology",
                    "score": mesh_score,
                    "max_score": mesh_max,
                    "status": mesh_status,
                    "summary": mesh_details_text,
                    "summary_i18n": {
                        "it": mesh_details_text,
                        "en": mesh_details_text_en
                    }
                },
                "wan_gateway": {
                    "key": "wan_gateway",
                    "score": wan_score,
                    "max_score": wan_max,
                    "status": wan_status,
                    "summary": wan_details_text,
                    "summary_i18n": {
                        "it": wan_details_text,
                        "en": wan_details_text_en
                    }
                },
                "client_signal": {
                    "key": "client_signal",
                    "score": client_score,
                    "max_score": client_max,
                    "status": client_status,
                    "summary": client_details_text,
                    "summary_i18n": {
                        "it": client_details_text,
                        "en": client_details_text_en
                    },
                    "weak_count": total_degraded,
                },
                "channel_density": {
                    "key": "channel_density",
                    "score": channel_score,
                    "max_score": channel_max,
                    "status": channel_status,
                    "summary": channel_details_text,
                    "summary_i18n": {
                        "it": channel_details_text,
                        "en": channel_details_text_en
                    },
                    "counts": {
                        "band_6ghz": c_6g,
                        "band_5ghz": c_5g,
                        "band_24ghz": c_24g,
                        "wired": sum(1 for d in connected_clients if not d.get("wireless"))
                    }
                }
            },
            "recommendations": recommendations,
            "recommendations_i18n": recommendations_i18n,
            "metrics": {
                "total_nodes": len(eeros),
                "online_nodes": len(eeros) - len(offline_nodes),
                "offline_nodes": len(offline_nodes),
                "connected_clients": len(connected_clients),
                "wireless_clients": len(wireless_connected),
                "weak_signal_clients": total_degraded,
                "ping_ms": float(network_details.get("speedtest", {}).get("ping_ms") or 0.0)
            }
        }

    async def _poll_loop(self):
        # Primo popolamento immediato
        await self._poll_and_cache()
        
        while self._running:
            try:
                poll_interval = int(await db_service.get_setting("poll_interval", str(settings.poll_interval)))
                await asyncio.sleep(poll_interval)
                await self._poll_and_cache()
                await self._run_periodic_jobs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Errore durante il ciclo di polling in background: {e}", exc_info=True)
                await asyncio.sleep(10)

    async def _poll_and_cache(self):
        try:
            # Caricamento iniziale MAC noti dal database SQLite
            if not self._initial_macs_loaded:
                try:
                    db_macs = await db_service.get_known_device_macs()
                    self._known_macs.update(db_macs)
                    self._initial_macs_loaded = True
                except Exception as e:
                    logger.warning(f"Error loading known MACs from DB: {e}")

            # 1. Recupero dati da eero client
            network_details = await eero_client.get_network_details()
            eeros = await eero_client.get_eeros()
            devices = await eero_client.get_devices()
            try:
                profiles = await eero_client.get_profiles()
            except Exception as ep:
                logger.warning(f"Failed to fetch profiles in poller: {ep}")
                profiles = []

            try:
                forwards_res = await eero_client.get_forwards_and_reservations()
                cloud_reservations = {
                    (r.get("mac") or r.get("mac_address") or "").lower().strip(): (r.get("ip") or r.get("ip_address") or "").strip() 
                    for r in forwards_res.get("reservations", [])
                    if isinstance(r, dict) and (r.get("mac") or r.get("mac_address"))
                }
            except Exception as e:
                logger.warning(f"Failed to fetch cloud reservations in poller: {e}")
                cloud_reservations = {}

            # Costruzione mappa dispositivi -> profili per arricchimento immediato
            # Costruzione mappa dispositivi -> profili per arricchimento immediato
            device_to_profile: Dict[str, Dict[str, Any]] = {}
            for prof in profiles:
                p_id = str(prof.get("id") or "")
                p_name = prof.get("name")
                for p_dev in prof.get("devices", []):
                    if isinstance(p_dev, dict):
                        p_mac = (p_dev.get("mac") or p_dev.get("mac_address") or "").lower()
                        p_dev_id = str(p_dev.get("id") or "")
                        p_dev_url = str(p_dev.get("url") or "")
                        if p_mac:
                            device_to_profile[p_mac] = {"profile_id": p_id, "profile_name": p_name}
                        if p_dev_id:
                            device_to_profile[p_dev_id] = {"profile_id": p_id, "profile_name": p_name}
                        if p_dev_url:
                            device_to_profile[p_dev_url] = {"profile_id": p_id, "profile_name": p_name}
                    elif isinstance(p_dev, str):
                        device_to_profile[p_dev] = {"profile_id": p_id, "profile_name": p_name}
                        device_to_profile[p_dev.split("/")[-1]] = {"profile_id": p_id, "profile_name": p_name}

            # 2. Arricchimento dispositivi con metadati locali e profilo utente cloud
            metadata_map = await db_service.get_all_device_metadata()
            enriched_devices = []
            device_metrics_batch = []
            
            total_dl_rate = 0.0
            total_ul_rate = 0.0
            total_rx = 0.0
            total_tx = 0.0

            now_utc = datetime.now(timezone.utc)
            dt_sec = (now_utc - self._prev_poll_time).total_seconds() if self._prev_poll_time else float(settings.poll_interval)
            dt_sec = max(1.0, min(120.0, dt_sec))
            self._prev_poll_time = now_utc

            is_initial_discovery = len(self._known_macs) == 0

            for dev in devices:
                mac = (dev.get("mac") or dev.get("mac_address") or "").lower()
                dev_id_str = str(dev.get("id") or "")
                dev_url_str = str(dev.get("url") or "")
                meta = metadata_map.get(mac, {})
                cloud_res_ip = cloud_reservations.get(mac)
                static_ip_val = cloud_res_ip or meta.get("static_ip", "")
                is_static = bool(cloud_res_ip or meta.get("static_ip") or dev.get("is_static"))
                
                # Profilo utente associato (da mappa profiles o dal campo diretto del dispositivo)
                prof_info = device_to_profile.get(mac) or device_to_profile.get(dev_id_str) or device_to_profile.get(dev_url_str) or {}
                if not prof_info and isinstance(dev.get("profile"), dict):
                    d_prof = dev["profile"]
                    prof_info = {
                        "profile_id": str(d_prof.get("id") or (d_prof.get("url", "").split("/")[-1] if d_prof.get("url") else "")),
                        "profile_name": d_prof.get("name")
                    }
                
                # Controllo eventuale override profilo dal database locale
                meta_pid = meta.get("profile_id")
                if meta_pid == "NONE":
                    final_prof_id = None
                    final_prof_name = None
                elif meta_pid:
                    final_prof_id = meta_pid
                    target_p = next((p for p in profiles if p.get("id") == meta_pid or p.get("url", "").endswith(meta_pid)), None)
                    final_prof_name = target_p.get("name") if target_p else None
                else:
                    final_prof_id = prof_info.get("profile_id")
                    final_prof_name = prof_info.get("profile_name")
                
                dev_copy = dict(dev)
                dev_copy["mac"] = mac
                dev_copy["profile_id"] = final_prof_id
                dev_copy["profile_name"] = final_prof_name
                dev_copy["custom_name"] = meta.get("custom_name") or dev.get("nickname") or dev.get("hostname")
                
                # Categoria & Icona (Issue #13): priorità personalizzazione utente > categoria nativa eero > fallback
                meta_cat = meta.get("category")
                if meta_cat and str(meta_cat).strip() and str(meta_cat).strip() != "Altro":
                    dev_copy["category"] = str(meta_cat).strip()
                else:
                    dev_copy["category"] = dev.get("default_category") or dev.get("category") or "Altro"

                meta_icon = meta.get("custom_icon")
                if meta_icon and str(meta_icon).strip() and str(meta_icon).strip() != "device":
                    dev_copy["custom_icon"] = str(meta_icon).strip()
                else:
                    dev_copy["custom_icon"] = dev.get("default_icon") or dev.get("custom_icon") or "device"

                dev_copy["custom_notes"] = meta.get("custom_notes", "")
                dev_copy["static_ip"] = static_ip_val
                dev_copy["is_static"] = is_static
                dev_copy["is_favorite"] = bool(meta.get("is_favorite", False))
                dev_copy["is_low_latency_target"] = bool(meta.get("is_low_latency_target", False))
                is_prof_paused = False
                if final_prof_id:
                    target_p = next((p for p in profiles if str(p.get("id")) == str(final_prof_id) or p.get("url", "").endswith(str(final_prof_id))), None)
                    if target_p and (target_p.get("paused") is True or target_p.get("is_paused") is True):
                        is_prof_paused = True

                is_cloud_paused = bool(dev.get("paused") is True or dev.get("is_paused") is True or is_prof_paused)
                dev_copy["paused"] = is_cloud_paused
                dev_copy["is_paused"] = is_cloud_paused
                dev_copy["is_local_paused"] = False
                enriched_devices.append(dev_copy)

                # Gestione Rilevamento Nuovo Dispositivo & Persistenza DB
                if mac:
                    if not is_initial_discovery and mac not in self._known_macs:
                        # Nuovo dispositivo autentico rilevato durante l'operatività
                        self._known_macs.add(mac)
                        asyncio.create_task(db_service.register_known_device(
                            mac=mac,
                            hostname=dev_copy.get("custom_name") or dev_copy.get("hostname", ""),
                            ip=dev_copy.get("ip", ""),
                            notified=True
                        ))
                        asyncio.create_task(notification_service.notify_new_device(dev_copy))
                        asyncio.create_task(adguard_service.auto_sync_if_enabled(enriched_devices))
                    else:
                        self._known_macs.add(mac)

            # Se era la primissima discovery assoluta (db vuoto), registriamo tutto su SQLite senza inviare notifiche
            if is_initial_discovery and enriched_devices:
                await db_service.register_known_devices_batch(enriched_devices, notified=True)

            # 2.5 Risoluzione robusta dei nodi eero per ciascun dispositivo
            eero_by_key: Dict[str, Dict[str, Any]] = {}
            gateway_node = None
            for node in eeros:
                if node.get("is_gateway") and not gateway_node:
                    gateway_node = node

                n_id = str(node.get("id") or "").strip()
                n_serial = str(node.get("serial") or "").strip()
                n_url = str(node.get("url") or "").strip()
                n_url_tail = n_url.split("/")[-1] if n_url else ""
                n_name = str(node.get("name") or node.get("location") or "").strip()
                n_ip = str(node.get("ip") or "").strip()

                for key in [n_id, n_serial, n_url, n_url_tail, n_name.lower(), n_ip]:
                    if key:
                        eero_by_key[key] = node

            if not gateway_node and eeros:
                gateway_node = eeros[0]

            for dev_copy in enriched_devices:
                cand_keys = [
                    str(dev_copy.get("connected_eero_id") or "").strip(),
                    str(dev_copy.get("connected_eero_url") or "").strip(),
                    str(dev_copy.get("connected_eero_name") or "").strip().lower(),
                ]
                cand_keys = [k for k in cand_keys if k]

                matched_node = None
                for k in cand_keys:
                    if k in eero_by_key:
                        matched_node = eero_by_key[k]
                        break
                    if "/" in k and k.split("/")[-1] in eero_by_key:
                        matched_node = eero_by_key[k.split("/")[-1]]
                        break

                if matched_node:
                    dev_copy["connected_eero_id"] = str(matched_node.get("id") or "")
                    dev_copy["connected_eero_name"] = str(matched_node.get("name") or matched_node.get("location") or "eero")
                elif dev_copy.get("connected"):
                    # Dispositivi cablati o reti a singolo nodo: attribuzione automatica al gateway se non specificato
                    if not dev_copy.get("wireless") or dev_copy.get("connection_type") == "wired" or len(eeros) == 1:
                        if gateway_node:
                            dev_copy["connected_eero_id"] = str(gateway_node.get("id") or "")
                            dev_copy["connected_eero_name"] = str(gateway_node.get("name") or gateway_node.get("location") or "Gateway")

            # 3. Distribuzione conteggio client connessi per singolo nodo eero
            for node in eeros:
                n_id = str(node.get("id") or "").strip()
                n_serial = str(node.get("serial") or "").strip()
                n_name = str(node.get("name") or node.get("location") or "").strip().lower()
                n_url = str(node.get("url") or "").strip()
                n_url_tail = n_url.split("/")[-1] if n_url else ""

                node_ident_keys = {k for k in [n_id, n_serial, n_name, n_url, n_url_tail] if k}

                matched_clients = [
                    d for d in enriched_devices
                    if d.get("connected") and (
                        str(d.get("connected_eero_id", "")).strip() in node_ident_keys or
                        str(d.get("connected_eero_name", "")).strip().lower() == n_name or
                        (node.get("is_gateway") and not d.get("connected_eero_id") and not d.get("wireless"))
                    )
                ]
                node["connected_clients_count"] = len(matched_clients)

            # 3.5 Campionamento continuo Segnale RSSI dispositivi wireless (v1.04.00)
            if not getattr(eero_client, "is_demo_mode", False):
                wireless_samples = [
                    d for d in enriched_devices
                    if d.get("connected") and d.get("wireless") and d.get("signal_rssi") is not None
                ]
                if wireless_samples:
                    asyncio.create_task(db_service.record_device_signal_samples(wireless_samples, is_demo=0))

            # Rilevamento nodi eero offline
            for node in eeros:
                node_id = str(node.get("id") or node.get("serial"))
                status = "online" if node.get("status") in ("online", "green") else "offline"
                if node_id in self._known_eeros_status:
                    prev_status = self._known_eeros_status[node_id]
                    if prev_status == "online" and status != "online":
                        asyncio.create_task(notification_service.notify_node_offline(node))
                self._known_eeros_status[node_id] = status

            # 4. Calcolo Network Health Score & Breakdown Dettagliato (Issue #15)
            health_details = self.calculate_health_details(network_details, eeros, enriched_devices)
            self.cached_health_score = health_details["score"]
            self.cached_health_details = health_details

            # 5. Aggiornamento Cache RAM
            self.cached_network = network_details
            self.cached_eeros = eeros
            self.cached_devices = enriched_devices
            self.cached_profiles = profiles
            self._last_poll_time = datetime.now(timezone.utc)

            # 6. Sincronizzazione automatica Speed Test reale da eero Gateway
            sp = network_details.get("speedtest")
            if sp and isinstance(sp, dict) and sp.get("download_mbps"):
                down_val = round(float(sp["download_mbps"]), 2)
                up_val = round(float(sp.get("upload_mbps", 0)), 2)
                ping_val = round(float(sp.get("ping_ms", 0)), 1)
                
                history_sp = await db_service.get_speedtests(limit=1)
                should_save = False
                if not history_sp:
                    should_save = True
                else:
                    latest = history_sp[0]
                    # Se l'ultimo test registrato ha valori diversi
                    if abs(float(latest.get("download_mbps", 0)) - down_val) > 2.0 or abs(float(latest.get("upload_mbps", 0)) - up_val) > 2.0:
                        should_save = True
                
                if should_save:
                    await db_service.save_speedtest(
                        download_mbps=down_val,
                        upload_mbps=up_val,
                        ping_ms=ping_val,
                        server_name=f"{network_details.get('isp', 'eero Gateway')} (WAN SpeedTest)",
                        source="eero_gateway"
                    )

        except Exception as e:
            logger.error(f"Errore durante il salvataggio delle metriche di rete: {e}")

    async def _run_periodic_jobs(self):
        """Esecuzione scheduler notturno LED, pulizia retention e speedtest pianificati."""
        now = datetime.now()
        
        # A. Scheduler Modalità Notte LED
        night_mode_enabled = (await db_service.get_setting("night_mode_enabled", "false")).lower() == "true"
        if night_mode_enabled:
            start_str = await db_service.get_setting("night_mode_start", "23:00")
            end_str = await db_service.get_setting("night_mode_end", "07:00")
            try:
                sh, sm = map(int, start_str.split(":"))
                eh, em = map(int, end_str.split(":"))
                start_time = dt_time(sh, sm)
                end_time = dt_time(eh, em)
                curr_time = now.time()

                if start_time < end_time:
                    is_night = start_time <= curr_time <= end_time
                else:
                    is_night = curr_time >= start_time or curr_time <= end_time

                if is_night != self._last_night_mode_state:
                    self._last_night_mode_state = is_night
                    target_led_on = not is_night
                    logger.info(f"Night Mode Scheduler: Impostazione LED a {target_led_on}")
                    await eero_client.set_all_leds(target_led_on)
            except Exception as ex:
                logger.error(f"Errore calcolo scheduler night mode: {ex}")

        # B. Retention Cleanup (una volta ogni 24 ore)
        if not self._last_retention_run or (now - self._last_retention_run).total_seconds() > 86400:
            retention_days = int(await db_service.get_setting("history_retention_days", str(settings.history_retention_days)))
            await db_service.cleanup_old_data(retention_days)
            self._last_retention_run = now

        # C. Speedtest Pianificato
        speedtest_hours = int(await db_service.get_setting("speedtest_schedule_hours", str(settings.speedtest_interval_hours)))
        if speedtest_hours > 0:
            if not self._last_scheduled_speedtest or (now - self._last_scheduled_speedtest).total_seconds() > (speedtest_hours * 3600):
                self._last_scheduled_speedtest = now
                asyncio.create_task(speedtest_service.run_speedtest())

        # D. Daily Digest (ore 21:00)
        today_str = now.strftime("%Y-%m-%d")
        if now.hour == 21 and self._last_digest_date != today_str:
            self._last_digest_date = today_str
            digest_enabled = (await db_service.get_setting("daily_digest_enabled", "true")).lower() == "true"
            if digest_enabled:
                asyncio.create_task(self._send_daily_digest())
            else:
                logger.debug("Daily digest automatic dispatch is disabled in settings.")

        # E. Sincronizzazione periodica AdGuard Home (ogni 30 minuti)
        if self.cached_devices and (not self._last_adguard_sync or (now - self._last_adguard_sync).total_seconds() > 1800):
            self._last_adguard_sync = now
            asyncio.create_task(adguard_service.auto_sync_if_enabled(self.cached_devices))

    async def _send_daily_digest(self) -> Dict[str, Any]:
        try:
            stats = await db_service.get_speedtest_stats()
            
            # Calcolo dispositivi connessi e suddivisione per banda fisica
            connected_devices = [d for d in self.cached_devices if d.get("connected")]
            total_active = len(connected_devices)
            
            count_6ghz = sum(1 for d in connected_devices if "6" in str(d.get("wireless_band", "")))
            count_5ghz = sum(1 for d in connected_devices if "5" in str(d.get("wireless_band", "")))
            count_24ghz = sum(1 for d in connected_devices if "2.4" in str(d.get("wireless_band", "")))
            count_wired = sum(1 for d in connected_devices if d.get("wired") or "wired" in str(d.get("connection_type", "")).lower() or "cablato" in str(d.get("wireless_band", "")).lower())

            # Informazioni sui nodi mesh
            total_nodes = len(self.cached_eeros)
            online_nodes = sum(1 for e in self.cached_eeros if e.get("connected") or e.get("status") in ("connected", "online"))
            
            # Informazioni WAN e Speedtest Gateway
            net = self.cached_network or {}
            wan_down = net.get("speed_down_mbps") or stats.get("avg_download") or 0.0
            wan_up = net.get("speed_up_mbps") or stats.get("avg_upload") or 0.0
            wan_ping = net.get("ping_ms") or stats.get("avg_ping") or 0.0
            isp_name = net.get("isp") or "N/D"
            network_name = net.get("name") or "Rete eero"
            health_score = self.cached_health_score or 100

            digest_payload = {
                "network_name": network_name,
                "health_score": health_score,
                "isp": isp_name,
                "active_devices_count": total_active,
                "count_6ghz": count_6ghz,
                "count_5ghz": count_5ghz,
                "count_24ghz": count_24ghz,
                "count_wired": count_wired,
                "online_nodes": online_nodes,
                "total_nodes": total_nodes,
                "wan_down": wan_down,
                "wan_up": wan_up,
                "wan_ping": wan_ping,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await notification_service.notify_digest(digest_payload)
            return digest_payload
        except Exception as e:
            logger.error(f"Errore invio digest giornaliero: {e}", exc_info=True)
            raise e

    def update_cached_profiles(self, profiles: List[Dict[str, Any]]):
        """Aggiorna atomicamente i profili in RAM e re-indicizza le associazioni di tutti i dispositivi in cache."""
        self.cached_profiles = profiles
        device_to_profile: Dict[str, Dict[str, Any]] = {}
        for prof in profiles:
            p_id = prof.get("id")
            p_name = prof.get("name")
            for p_dev in prof.get("devices", []):
                p_mac = (p_dev.get("mac") or "").lower()
                p_dev_id = str(p_dev.get("id") or "")
                p_url = p_dev.get("url") or ""
                if p_mac:
                    device_to_profile[p_mac] = {"profile_id": p_id, "profile_name": p_name}
                if p_dev_id:
                    device_to_profile[p_dev_id] = {"profile_id": p_id, "profile_name": p_name}
                if p_url:
                    device_to_profile[p_url] = {"profile_id": p_id, "profile_name": p_name}

        for d in self.cached_devices:
            d_mac = (d.get("mac") or "").lower()
            d_id = str(d.get("id") or "")
            d_url = d.get("url") or ""
            info = device_to_profile.get(d_mac) or device_to_profile.get(d_id) or device_to_profile.get(d_url)
            if info:
                d["profile_id"] = info["profile_id"]
                d["profile_name"] = info["profile_name"]
            else:
                d["profile_id"] = None
                d["profile_name"] = None


# Istanza singleton background poller
background_poller = BackgroundPoller()
