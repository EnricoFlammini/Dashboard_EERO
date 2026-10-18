import asyncio
import logging
import os
import zoneinfo
from datetime import datetime, timezone, time as dt_time
from typing import Any, Dict, List, Optional, Set

from app.config import settings
from app.i18n import SUPPORTED_LANGUAGES, current_language, tr, tr_all
from app.services.adguard import adguard_service
from app.services.db import db_service
from app.services.eero_client import eero_client
from app.services.notifications import notification_service
from app.services.speedtest_service import speedtest_service

logger = logging.getLogger(__name__)


# Chiavi con credenziali Wi-Fi nel payload eero (/2.2/networks/{id}): mai esposte dalla cache pubblica
_WIFI_SECRET_KEYS = {"password", "passphrase", "psk", "network_key", "wpa_key", "pppoe_password"}


def _without_wifi_passwords(value: Any) -> Any:
    """Copia dei dettagli rete senza password Wi-Fi, a qualsiasi livello (rete principale, ospiti, ...).

    Il cloud eero restituisce la password della rete principale ("password") e quella della rete ospiti
    in /2.2/networks/{id}: la cache RAM è servita da GET pubblici (/api/network/overview), quindi non deve
    contenerle. La rete ospiti resta consultabile dall'endpoint dedicato /api/network/guest (QR Code).
    """
    if isinstance(value, dict):
        return {k: _without_wifi_passwords(v) for k, v in value.items() if str(k).lower() not in _WIFI_SECRET_KEYS}
    if isinstance(value, list):
        return [_without_wifi_passwords(v) for v in value]
    return value


def _tr_each(key: str, **params: Any) -> Dict[str, str]:
    """Like tr_all, but a param given as {"en": ..., "it": ...} is resolved per language."""
    return {
        lang: tr(key, lang=lang, **{k: (v.get(lang, "") if isinstance(v, dict) else v) for k, v in params.items()})
        for lang in SUPPORTED_LANGUAGES
    }


def _join_issues(issues: List[Dict[str, str]]) -> Dict[str, str]:
    """Joins bilingual issue texts into one bilingual pillar summary."""
    return {lang: "; ".join(issue[lang] for issue in issues) for lang in SUPPORTED_LANGUAGES}


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
        self.cached_iot_anomalies: List[Dict[str, Any]] = []
        
        # Tracking states for alert detection
        self._known_macs: Set[str] = set()
        self._initial_macs_loaded: bool = False
        self._known_eeros_status: Dict[str, str] = {}
        self._last_night_mode_state: Optional[bool] = None
        self._last_retention_run: Optional[datetime] = None
        self._last_scheduled_speedtest: Optional[datetime] = None
        self._last_digest_date: Optional[str] = None
        self._last_adguard_sync: Optional[datetime] = None
        self._last_eero_news_run: Optional[datetime] = None
        self._prev_device_metrics: Dict[str, Dict[str, Any]] = {}
        self._prev_poll_time: Optional[datetime] = None
        self._prev_connected_wireless_macs: Set[str] = set()

        # Cloud Resilience & Graceful Disconnection (Issue #55)
        self._consecutive_failed_polls: int = 0
        self._last_successful_poll: Optional[datetime] = None
        self.data_stale: bool = False
        self.cloud_status: str = "connected"
        self._cloud_alert_sent: bool = False

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

    def mark_cached_devices_seen(self, macs: Set[str], seen: bool = True):
        """Aggiorna subito il badge NUOVO nella cache RAM, senza attendere il prossimo ciclo di polling."""
        for d in self.cached_devices:
            mac = (d.get("mac") or d.get("mac_address") or "").lower()
            if mac not in macs:
                continue
            if seen and d.get("is_new"):
                d.update(is_new=False, is_new_24h=False, new_dismissed=True)
            elif not seen and d.get("new_dismissed"):
                d.update(is_new=True, new_dismissed=False)

    def invalidate_cache(self):
        """Invalida completamente la cache in RAM per consentire l'hot-swap immediato tra reti."""
        self.cached_network = {}
        self.cached_eeros = []
        self.cached_devices = []
        self.cached_profiles = []
        self.cached_health_score = 100
        self.cached_health_details = {}
        self.cached_iot_anomalies = []
        self._prev_device_metrics = {}
        logger.info("Poller RAM cache invalidated.")

    def get_cached_state(self) -> Dict[str, Any]:
        """Restituisce istantaneamente lo stato in RAM con latenza zero."""
        return {
            "network": self.cached_network,
            "eeros": self.cached_eeros,
            "devices": self.cached_devices,
            "profiles": self.cached_profiles,
            "health_score": self.cached_health_score,
            "health_details": self.cached_health_details,
            "iot_anomalies": self.cached_iot_anomalies,
            "last_poll_time": self._last_successful_poll.isoformat() if self._last_successful_poll else (self._last_poll_time.isoformat() if self._last_poll_time else None),
            "last_successful_poll": self._last_successful_poll.isoformat() if self._last_successful_poll else None,
            "data_stale": self.data_stale,
            "cloud_status": self.cloud_status,
            "consecutive_failed_polls": self._consecutive_failed_polls,
            "is_authenticated": eero_client.is_authenticated,
            "demo_mode": settings.demo_mode or (eero_client.user_token and eero_client.user_token.startswith("demo_")),
            "active_network_id": eero_client.current_network_id,
            "available_networks": eero_client.get_available_networks(),
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
        lang_now = current_language()

        def add_recommendation(text_i18n: Dict[str, str]) -> None:
            recommendations.append(text_i18n[lang_now])
            recommendations_i18n.append(text_i18n)

        # 1. Mesh Topology & Nodes (Max 40 pt)
        mesh_max = 40
        mesh_score = mesh_max
        mesh_issues: List[Dict[str, str]] = []

        offline_nodes = [e for e in eeros if e.get("status") not in ("online", "green", "rebooting")]
        if offline_nodes:
            deduction = len(offline_nodes) * 20
            mesh_score = max(0, mesh_score - deduction)
            names_i18n = {
                lang: [e.get("name") or e.get("location") or tr("health.fallback_node_name", lang=lang) for e in offline_nodes]
                for lang in SUPPORTED_LANGUAGES
            }
            names_str_i18n = {lang: ", ".join(names) for lang, names in names_i18n.items()}
            mesh_issues.append(_tr_each("health.issue_offline_nodes", count=len(offline_nodes), names=names_str_i18n))
            title_i18n = tr_all("health.penalty_offline_nodes_title")
            description_i18n = tr_all("health.penalty_offline_nodes_desc", count=len(offline_nodes))
            penalties.append({
                "id": "offline_nodes",
                "pillar": "mesh_topology",
                "title": title_i18n[lang_now],
                "title_i18n": title_i18n,
                "impact": -min(deduction, mesh_max),
                "severity": "critical",
                "description": description_i18n[lang_now],
                "description_i18n": description_i18n,
                "affected_items": names_i18n[lang_now]
            })
            add_recommendation(_tr_each("health.rec_offline_nodes", names=names_str_i18n))

        # Verifica degradamento backhaul su nodi wireless o cablati
        degraded_backhaul_nodes: List[Dict[str, str]] = []
        for e in eeros:
            if e.get("status") in ("online", "green") and not e.get("is_gateway"):
                rssi = e.get("signal_rssi")
                if isinstance(rssi, (int, float)) and rssi < -75:
                    degraded_backhaul_nodes.append(tr_all("health.item_weak_backhaul", name=e.get("name"), rssi=rssi))
                backhaul_str = str(e.get("backhaul_type") or "").lower()
                if "100 mbps" in backhaul_str or "100m" in backhaul_str:
                    degraded_backhaul_nodes.append(tr_all("health.item_cable_100", name=e.get("name")))

        if degraded_backhaul_nodes and mesh_score > 5:
            backhaul_deduction = min(len(degraded_backhaul_nodes) * 5, 10)
            mesh_score = max(0, mesh_score - backhaul_deduction)
            mesh_issues.append(tr_all("health.issue_degraded_backhaul", count=len(degraded_backhaul_nodes)))
            title_i18n = tr_all("health.penalty_degraded_backhaul_title")
            description_i18n = tr_all("health.penalty_degraded_backhaul_desc")
            penalties.append({
                "id": "degraded_backhaul",
                "pillar": "mesh_topology",
                "title": title_i18n[lang_now],
                "title_i18n": title_i18n,
                "impact": -backhaul_deduction,
                "severity": "warning",
                "description": description_i18n[lang_now],
                "description_i18n": description_i18n,
                "affected_items": [item[lang_now] for item in degraded_backhaul_nodes]
            })
            add_recommendation(tr_all("health.rec_degraded_backhaul"))

        mesh_status = "optimal" if mesh_score >= 35 else ("warning" if mesh_score >= 20 else "critical")
        mesh_summary_i18n = _join_issues(mesh_issues) if mesh_issues else tr_all(
            "health.mesh_summary_ok", online=len(eeros) - len(offline_nodes), total=len(eeros)
        )

        # 2. WAN & Gateway Connectivity (Max 30 pt)
        wan_max = 30
        wan_score = wan_max
        wan_issues: List[Dict[str, str]] = []

        is_wan_online = network_details.get("status") in ("online", "green")
        if not is_wan_online:
            wan_score = 0
            wan_issues.append(tr_all("health.issue_wan_offline"))
            title_i18n = tr_all("health.penalty_wan_offline_title")
            description_i18n = tr_all("health.penalty_wan_offline_desc")
            penalties.append({
                "id": "wan_offline",
                "pillar": "wan_gateway",
                "title": title_i18n[lang_now],
                "title_i18n": title_i18n,
                "impact": -wan_max,
                "severity": "critical",
                "description": description_i18n[lang_now],
                "description_i18n": description_i18n,
                "affected_items": [tr("health.item_wan_gateway")]
            })
            add_recommendation(tr_all("health.rec_wan_offline"))
        else:
            sp = network_details.get("speedtest") or {}
            ping_val = float(sp.get("ping_ms") or 0.0)
            ping_str = f"{ping_val:.1f}"
            if ping_val > 80.0:
                wan_score = max(10, wan_score - 10)
                wan_issues.append(tr_all("health.issue_high_latency", ping=ping_str))
                title_i18n = tr_all("health.penalty_high_latency_title")
                description_i18n = tr_all("health.penalty_high_latency_desc", ping=ping_str)
                penalties.append({
                    "id": "high_wan_latency",
                    "pillar": "wan_gateway",
                    "title": title_i18n[lang_now],
                    "title_i18n": title_i18n,
                    "impact": -10,
                    "severity": "warning",
                    "description": description_i18n[lang_now],
                    "description_i18n": description_i18n,
                    "affected_items": [tr("health.item_ping_gateway", ping=ping_str)]
                })
                add_recommendation(tr_all("health.rec_high_latency"))
            elif ping_val > 45.0:
                wan_score = max(20, wan_score - 5)
                wan_issues.append(tr_all("health.issue_moderate_latency", ping=ping_str))
                title_i18n = tr_all("health.penalty_moderate_latency_title")
                description_i18n = tr_all("health.penalty_moderate_latency_desc", ping=ping_str)
                penalties.append({
                    "id": "moderate_wan_latency",
                    "pillar": "wan_gateway",
                    "title": title_i18n[lang_now],
                    "title_i18n": title_i18n,
                    "impact": -5,
                    "severity": "info",
                    "description": description_i18n[lang_now],
                    "description_i18n": description_i18n,
                    "affected_items": [tr("health.item_ping", ping=ping_str)]
                })

        wan_status = "optimal" if wan_score >= 25 else ("warning" if wan_score >= 15 else "critical")
        if wan_issues:
            wan_summary_i18n = _join_issues(wan_issues)
        else:
            public_ip = network_details.get("public_ip")
            wan_summary_i18n = _tr_each(
                "health.wan_summary_ok",
                ip=public_ip if public_ip is not None else tr_all("health.not_available"),
            )

        # 3. Client Wi-Fi Signal Quality (Max 20 pt)
        client_max = 20
        client_score = client_max
        client_issues: List[Dict[str, str]] = []

        connected_clients = [d for d in enriched_devices if d.get("connected")]
        wireless_connected = [d for d in connected_clients if d.get("wireless")]

        weak_devices: List[Dict[str, str]] = []
        critical_devices: List[Dict[str, str]] = []
        for d in wireless_connected:
            rssi = d.get("signal_rssi")
            if isinstance(rssi, (int, float)):
                d_name = d.get("custom_name") or d.get("nickname") or d.get("hostname") or d.get("mac") or tr_all("health.fallback_device_name")
                eero_name = d.get("connected_eero_name") or "eero"
                item_label = _tr_each("health.item_weak_client", device=d_name, rssi=rssi, node=eero_name)
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
            client_issues.append(tr_all("health.issue_weak_clients", count=total_degraded))
            title_i18n = tr_all("health.penalty_weak_clients_title")
            description_i18n = tr_all("health.penalty_weak_clients_desc", count=total_degraded)
            penalties.append({
                "id": "weak_client_signal",
                "pillar": "client_signal",
                "title": title_i18n[lang_now],
                "title_i18n": title_i18n,
                "impact": -deduction,
                "severity": "warning" if len(critical_devices) == 0 else "critical",
                "description": description_i18n[lang_now],
                "description_i18n": description_i18n,
                "affected_items": [item[lang_now] for item in all_affected[:6]]
            })
            devices_i18n = {lang: ", ".join(item[lang] for item in all_affected[:3]) for lang in SUPPORTED_LANGUAGES}
            add_recommendation(_tr_each("health.rec_weak_clients", devices=devices_i18n))

        client_status = "optimal" if client_score >= 18 else ("warning" if client_score >= 10 else "critical")
        client_summary_i18n = _join_issues(client_issues) if client_issues else tr_all(
            "health.client_summary_ok", count=len(wireless_connected)
        )

        # 4. Channel Distribution & Density (Max 10 pt)
        channel_max = 10
        channel_score = channel_max
        channel_issues: List[Dict[str, str]] = []

        c_6g = sum(1 for d in wireless_connected if "6" in str(d.get("wireless_band", "")))
        c_5g = sum(1 for d in wireless_connected if "5" in str(d.get("wireless_band", "")))
        c_24g = sum(1 for d in wireless_connected if "2.4" in str(d.get("wireless_band", "")))
        total_w = len(wireless_connected)

        if total_w >= 6 and (c_24g / total_w) > 0.70 and (c_5g + c_6g) > 0:
            channel_score = max(5, channel_score - 3)
            channel_issues.append(tr_all("health.issue_band_24"))
            title_i18n = tr_all("health.penalty_band_24_title")
            description_i18n = tr_all("health.penalty_band_24_desc", count=c_24g, total=total_w)
            penalties.append({
                "id": "band_24_crowding",
                "pillar": "channel_density",
                "title": title_i18n[lang_now],
                "title_i18n": title_i18n,
                "impact": -3,
                "severity": "info",
                "description": description_i18n[lang_now],
                "description_i18n": description_i18n,
                "affected_items": [
                    tr("health.item_band_clients", band="2.4 GHz", count=c_24g),
                    tr("health.item_band_clients", band="5 GHz", count=c_5g),
                    tr("health.item_band_clients", band="6 GHz", count=c_6g),
                ]
            })
            add_recommendation(tr_all("health.rec_band_24"))

        if len(eeros) > 1 and total_w >= 8:
            for node in eeros:
                cnt = node.get("connected_clients_count", 0)
                if cnt / len(connected_clients) > 0.80 and cnt >= 15:
                    node_name = node.get("name") or tr_all("health.fallback_node_short")
                    channel_score = max(4, channel_score - 3)
                    channel_issues.append(_tr_each("health.issue_node_overload", node=node_name, count=cnt))
                    title_i18n = tr_all("health.penalty_node_overload_title")
                    description_i18n = _tr_each("health.penalty_node_overload_desc", node=node_name)
                    penalties.append({
                        "id": "node_overload",
                        "pillar": "channel_density",
                        "title": title_i18n[lang_now],
                        "title_i18n": title_i18n,
                        "impact": -3,
                        "severity": "info",
                        "description": description_i18n[lang_now],
                        "description_i18n": description_i18n,
                        "affected_items": [_tr_each("health.item_node_clients", node=node_name, count=cnt)[lang_now]]
                    })
                    break

        channel_status = "optimal" if channel_score >= 8 else ("warning" if channel_score >= 5 else "critical")
        channel_summary_i18n = _join_issues(channel_issues) if channel_issues else tr_all(
            "health.channel_summary_ok", c6=c_6g, c5=c_5g, c24=c_24g
        )

        # Calcolo Score Finale (1 - 100)
        total_score = mesh_score + wan_score + client_score + channel_score
        final_score = max(5, min(100, total_score))

        overall_status = "optimal" if final_score >= 90 else ("good" if final_score >= 70 else ("warning" if final_score >= 50 else "critical"))

        if not recommendations:
            add_recommendation(tr_all("health.rec_all_optimal"))

        # Diagnostica Intelligente AI & Roaming Advisor (v1.6.0 Modulo 1)
        from app.services.diagnostics_service import diagnostics_service

        roaming_info = diagnostics_service.analyze_roaming_advisor(enriched_devices, eeros)
        recent_anomalies = getattr(self, "cached_iot_anomalies", [])
        ai_summary = diagnostics_service.generate_health_summary(
            health_details={
                "score": final_score,
                "status": overall_status,
                "penalties": penalties,
            },
            network_details=network_details,
            eeros=eeros,
            devices=enriched_devices,
            roaming_info=roaming_info,
            recent_anomalies=recent_anomalies,
        )

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
                    "summary": mesh_summary_i18n[lang_now],
                    "summary_i18n": mesh_summary_i18n
                },
                "wan_gateway": {
                    "key": "wan_gateway",
                    "score": wan_score,
                    "max_score": wan_max,
                    "status": wan_status,
                    "summary": wan_summary_i18n[lang_now],
                    "summary_i18n": wan_summary_i18n
                },
                "client_signal": {
                    "key": "client_signal",
                    "score": client_score,
                    "max_score": client_max,
                    "status": client_status,
                    "summary": client_summary_i18n[lang_now],
                    "summary_i18n": client_summary_i18n,
                    "weak_count": total_degraded,
                },
                "channel_density": {
                    "key": "channel_density",
                    "score": channel_score,
                    "max_score": channel_max,
                    "status": channel_status,
                    "summary": channel_summary_i18n[lang_now],
                    "summary_i18n": channel_summary_i18n,
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
            "ai_summary": ai_summary,
            "roaming_advisor": roaming_info,
            "iot_anomalies": recent_anomalies,
            "action_checklist": ai_summary.get("checklist", []),
            "metrics": {
                "total_nodes": len(eeros),
                "online_nodes": len(eeros) - len(offline_nodes),
                "offline_nodes": len(offline_nodes),
                "connected_clients": len(connected_clients),
                "wireless_clients": len(wireless_connected),
                "weak_signal_clients": total_degraded,
                "ping_ms": float(network_details.get("speedtest", {}).get("ping_ms") or 0.0),
                "sticky_roaming_clients": roaming_info.get("sticky_count", 0),
                "iot_anomalies_count": len(recent_anomalies),
            }
        }

    async def _poll_loop(self):
        # Primo popolamento immediato
        await self._poll_and_cache()
        
        while self._running:
            try:
                base_interval = int(await db_service.get_setting("poll_interval", str(settings.poll_interval)))
                if self._consecutive_failed_polls > 0:
                    # Progressive backoff durante disconnessione o indisponibilità cloud (max 120s)
                    poll_interval = min(120, base_interval * min(self._consecutive_failed_polls + 1, 4))
                else:
                    poll_interval = base_interval
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

            # 1. Recupero dati da eero client con resilienza ad outage/timeout cloud (Issue #55)
            try:
                network_details = await eero_client.get_network_details()
                eeros = await eero_client.get_eeros()
                devices = await eero_client.get_devices()
            except Exception as e:
                self._consecutive_failed_polls += 1
                self.data_stale = True
                err_str = str(e).lower()
                status_code = getattr(getattr(e, "response", None), "status_code", None)
                if status_code == 401 or "401" in err_str or "unauthorized" in err_str or "expired" in err_str:
                    self.cloud_status = "unauthorized"
                else:
                    self.cloud_status = "unreachable"

                logger.warning(
                    f"Cloud poll attempt failed ({self._consecutive_failed_polls} consecutive failure(s), "
                    f"cloud_status='{self.cloud_status}'): {e}"
                )

                if self._consecutive_failed_polls >= 3 and not self._cloud_alert_sent:
                    self._cloud_alert_sent = True
                    asyncio.create_task(notification_service.notify_cloud_unreachable(
                        reason=self.cloud_status,
                        consecutive_failures=self._consecutive_failed_polls
                    ))
                # Interrompi il ciclo senza aggiornare il timestamp di poll né i nodi/allarmi falsi
                return

            # Se la chiamata ha avuto successo e l'allarme era attivo, notifica il ripristino
            if self._cloud_alert_sent:
                asyncio.create_task(notification_service.notify_cloud_recovered())
                self._cloud_alert_sent = False

            self._consecutive_failed_polls = 0
            self.data_stale = False
            self.cloud_status = "connected"

            try:
                profiles = await eero_client.get_profiles()
            except Exception as ep:
                logger.warning(f"Failed to fetch profiles in poller: {ep}")
                profiles = []

            try:
                forwards_res = await eero_client.get_forwards_and_reservations()
                cloud_reservations = {}
                # Mappa di supporto per correlare MAC se la reservation contiene solo device URL o ID
                dev_lookup = {}
                for d in devices:
                    if isinstance(d, dict):
                        d_mac = (d.get("mac") or d.get("mac_address") or "").lower().strip()
                        if d_mac:
                            if d.get("id"):
                                dev_lookup[str(d["id"])] = d_mac
                            if d.get("url"):
                                dev_lookup[str(d["url"])] = d_mac
                            if d.get("ip"):
                                dev_lookup[str(d["ip"])] = d_mac

                for r in forwards_res.get("reservations", []):
                    if not isinstance(r, dict):
                        continue
                    r_mac = (r.get("mac") or r.get("mac_address") or "").lower().strip()
                    r_ip = (r.get("ip") or r.get("ip_address") or "").strip()
                    r_dev = str(r.get("device") or r.get("device_id") or "")
                    if not r_mac and r_dev:
                        r_mac = dev_lookup.get(r_dev) or dev_lookup.get(r_dev.split("/")[-1]) or ""
                    if not r_mac and r_ip:
                        r_mac = dev_lookup.get(r_ip) or ""
                    if r_mac and r_ip:
                        cloud_reservations[r_mac] = r_ip
            except Exception as e:
                logger.warning(f"Failed to fetch cloud reservations in poller: {e}")
                cloud_reservations = {}

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

            # 2. Arricchimento dispositivi con metadati locali, profilo utente cloud, Reverse NDP IPs (Issue #57) e First Seen (Issue #60)
            metadata_map = await db_service.get_all_device_metadata()
            discovered_ips_map = await db_service.get_all_discovered_ips_map()
            known_devices_map = await db_service.get_all_known_devices_map()
            enriched_devices = []
            device_metrics_batch = []
            
            total_dl_rate = 0.0
            total_ul_rate = 0.0
            total_rx = 0.0
            total_tx = 0.0

            now_utc = datetime.now(timezone.utc)
            dt_poll = (now_utc - self._prev_poll_time).total_seconds() if self._prev_poll_time else float(settings.poll_interval)
            dt_poll = max(1.0, min(120.0, dt_poll))

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
                dev_copy["dns_sync_excluded"] = bool(meta.get("dns_sync_excluded", False))
                is_prof_paused = False
                if final_prof_id:
                    target_p = next((p for p in profiles if str(p.get("id")) == str(final_prof_id) or p.get("url", "").endswith(str(final_prof_id))), None)
                    if target_p and (target_p.get("paused") is True or target_p.get("is_paused") is True):
                        is_prof_paused = True

                is_cloud_paused = bool(dev.get("paused") is True or dev.get("is_paused") is True or is_prof_paused)
                dev_copy["paused"] = is_cloud_paused
                dev_copy["is_paused"] = is_cloud_paused
                dev_copy["is_local_paused"] = False

                # Contatori hardware e calcolo volumi da pacchetti fisici reali (Stima Hardware in Tempo Reale)
                rx_b = float(dev_copy.get("rx_bytes") or 0.0)
                tx_b = float(dev_copy.get("tx_bytes") or 0.0)
                rx_pkts = int(dev_copy.get("rx_packets") or 0)
                tx_pkts = int(dev_copy.get("tx_packets") or 0)
                if rx_b == 0.0 and rx_pkts > 0:
                    rx_b = float(rx_pkts * 1420.0)
                    dev_copy["rx_bytes"] = rx_b
                if tx_b == 0.0 and tx_pkts > 0:
                    tx_b = float(tx_pkts * 280.0)
                    dev_copy["tx_bytes"] = tx_b

                # Arricchimento Reverse NDP / Discovered IPs (Issue #57)
                disc_for_dev = discovered_ips_map.get(mac, [])
                if disc_for_dev:
                    existing_ula = list(dev_copy.get("ipv6_ula") or [])
                    existing_all_v6 = list(dev_copy.get("ipv6_addresses") or [])
                    existing_details = list(dev_copy.get("ipv6_details") or [])

                    for disc in disc_for_dev:
                        d_ip = disc.get("ip_address")
                        d_type = (disc.get("ip_type") or "ULA").upper()
                        d_src = disc.get("source") or "ndp_enrichment"
                        if not d_ip:
                            continue

                        if d_ip not in existing_ula and d_type == "ULA":
                            existing_ula.append(d_ip)
                        if d_ip not in existing_all_v6:
                            existing_all_v6.append(d_ip)

                        if not any(entry.get("address") == d_ip for entry in existing_details):
                            existing_details.append({
                                "address": d_ip,
                                "type": d_type,
                                "scope": "local" if d_type == "ULA" else "global",
                                "origin": "ndp_discovered",
                                "source": d_src
                            })

                    dev_copy["ipv6_ula"] = existing_ula
                    dev_copy["ipv6_addresses"] = existing_all_v6
                    dev_copy["ipv6_all"] = existing_all_v6
                    dev_copy["ipv6_details"] = existing_details
                    dev_copy["has_discovered_ips"] = True
                    dev_copy["discovered_ips"] = disc_for_dev

                    # Promuovi a primario se il dispositivo non aveva IPv6 o aveva solo link-local
                    if not dev_copy.get("ipv6") or str(dev_copy.get("ipv6")).lower().startswith("fe80:"):
                        if existing_ula:
                            dev_copy["ipv6"] = existing_ula[0]

                # First Seen & New Device Detection (Issue #60 - @DannyFeliz)
                known_dev_entry = known_devices_map.get(mac, {})
                first_seen_str = known_dev_entry.get("first_seen")
                if not first_seen_str:
                    first_seen_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")

                dev_copy["first_seen"] = first_seen_str
                is_new_24h = False
                is_new_7d = False
                try:
                    fs_clean = str(first_seen_str).replace("Z", "+00:00")
                    if "T" in fs_clean:
                        fs_dt = datetime.fromisoformat(fs_clean)
                    else:
                        fs_dt = datetime.strptime(fs_clean[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    if fs_dt.tzinfo is None:
                        fs_dt = fs_dt.replace(tzinfo=timezone.utc)
                    age_sec = (now_utc - fs_dt).total_seconds()
                    is_new_24h = 0 <= age_sec <= 86400
                    is_new_7d = 0 <= age_sec <= (86400 * 7)
                except Exception:
                    pass

                # Badge NUOVO soppresso per i dispositivi della prima scansione (già in rete) o segnati come visti
                is_baseline = bool(known_dev_entry.get("baseline")) or (is_initial_discovery and not known_dev_entry)
                is_acknowledged = bool(known_dev_entry.get("acknowledged_at"))
                dev_copy["is_new"] = is_new_7d and not (is_baseline or is_acknowledged)
                dev_copy["is_new_24h"] = is_new_24h and not (is_baseline or is_acknowledged)
                dev_copy["is_baseline"] = is_baseline
                dev_copy["new_dismissed"] = is_new_7d and is_acknowledged and not is_baseline

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
                await db_service.register_known_devices_batch(enriched_devices, notified=True, baseline=True)

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

            # 3.5.1 Calcolo Throughput Real-Time effettivo basato sui delta dei contatori hardware (rx_bytes / tx_bytes)
            now_dt = datetime.now(timezone.utc)
            dt_sec = (now_dt - self._prev_poll_time).total_seconds() if self._prev_poll_time else dt_poll
            dt_sec = max(0.5, min(120.0, dt_sec))

            for dev_copy in enriched_devices:
                mac_key = (dev_copy.get("mac") or "").lower().strip()
                if not mac_key:
                    continue
                rx_now = float(dev_copy.get("rx_bytes") or 0.0)
                tx_now = float(dev_copy.get("tx_bytes") or 0.0)

                calc_down = float(dev_copy.get("download_rate_mbps") or 0.0)
                calc_up = float(dev_copy.get("upload_rate_mbps") or 0.0)

                if mac_key in self._prev_device_metrics and dt_sec > 0.5:
                    prev_data = self._prev_device_metrics[mac_key]
                    rx_prev = float(prev_data.get("rx_bytes") or 0.0)
                    tx_prev = float(prev_data.get("tx_bytes") or 0.0)

                    if rx_now >= rx_prev:
                        delta_rx = rx_now - rx_prev
                        rate_down = round((delta_rx * 8.0) / (dt_sec * 1_000_000.0), 2)
                        calc_down = max(calc_down, rate_down)

                    if tx_now >= tx_prev:
                        delta_tx = tx_now - tx_prev
                        rate_up = round((delta_tx * 8.0) / (dt_sec * 1_000_000.0), 2)
                        calc_up = max(calc_up, rate_up)

                dev_copy["download_rate_mbps"] = round(calc_down, 2)
                dev_copy["upload_rate_mbps"] = round(calc_up, 2)
                dev_copy["rx_rate"] = dev_copy["download_rate_mbps"]
                dev_copy["tx_rate"] = dev_copy["upload_rate_mbps"]
                self._prev_device_metrics[mac_key] = {"rx_bytes": rx_now, "tx_bytes": tx_now, "timestamp": now_dt}

            self._prev_poll_time = now_dt

            # 3.5 Campionamento continuo Segnale RSSI dispositivi wireless & Rilevamento Uscita/Departure
            if not getattr(eero_client, "is_demo_mode", False):
                wireless_samples = [
                    d for d in enriched_devices
                    if d.get("connected") and d.get("wireless") and d.get("signal_rssi") is not None
                ]
                if wireless_samples:
                    try:
                        await db_service.record_device_signal_samples(wireless_samples, is_demo=0)
                    except Exception as sig_err:
                        logger.warning(f"Device signal sampling error: {sig_err}")

                # Rilevamento disconnessione / uscita da casa per dispositivi wireless: bonifica campioni transitori
                current_connected_wireless_macs = {
                    str(d.get("mac") or d.get("mac_address") or "").lower().strip()
                    for d in enriched_devices
                    if d.get("connected") and d.get("wireless") and (d.get("mac") or d.get("mac_address"))
                }
                if self._prev_connected_wireless_macs:
                    disconnected_macs = self._prev_connected_wireless_macs - current_connected_wireless_macs
                    for d_mac in disconnected_macs:
                        if d_mac:
                            try:
                                await db_service.prune_device_exit_transient_samples(d_mac, window_minutes=5, threshold_rssi=-75, is_demo=0)
                            except Exception as prune_err:
                                logger.debug(f"Device prune error for {d_mac}: {prune_err}")
                self._prev_connected_wireless_macs = current_connected_wireless_macs

            # 3.6 Campionamento continuo Utilizzo Dati Dispositivi (v1.5.0 Insights Suite)
            try:
                curr_net = str(eero_client.current_network_id or "default")
                is_demo_flag = 1 if getattr(eero_client, "is_demo_mode", False) else 0
                usage_samples = [
                    d for d in enriched_devices
                    if d.get("mac") and (d.get("rx_bytes") is not None or d.get("download_rate_mbps") is not None)
                ]
                if usage_samples:
                    await db_service.record_device_usage_samples(usage_samples, network_id=curr_net, is_demo=is_demo_flag)
            except Exception as usage_err:
                logger.debug(f"Device usage sampling error: {usage_err}")

            # Rilevamento nodi eero offline (Issue #34) - Soppressione falsi allarmi durante interruzioni cloud (Issue #55)
            if self._consecutive_failed_polls == 0 and not self.data_stale:
                for node in eeros:
                    node_id = str(node.get("id") or node.get("serial"))
                    node_status = str(node.get("status") or "").lower()
                    status = "online" if node_status in ("online", "green") else ("rebooting" if node_status == "rebooting" else "offline")
                    if node_id in self._known_eeros_status:
                        prev_status = self._known_eeros_status[node_id]
                        # Allarme disconnessione solo per cadute impreviste (non per riavvii intenzionali)
                        if prev_status == "online" and status == "offline":
                            asyncio.create_task(notification_service.notify_node_offline(node))
                    self._known_eeros_status[node_id] = status

            # 3.7 Rilevamento / Aggiornamento Anomalie Traffico Notturno IoT (v1.6.0 Modulo 1)
            try:
                from app.services.diagnostics_service import diagnostics_service
                if getattr(eero_client, "is_demo_mode", False) or settings.demo_mode:
                    self.cached_iot_anomalies = diagnostics_service.detect_iot_night_anomalies(enriched_devices, [], is_demo=True)
                else:
                    self.cached_iot_anomalies = await db_service.get_iot_anomalies(limit=20)
            except Exception as anom_err:
                logger.debug(f"IoT anomalies loading error: {anom_err}")

            # 4. Calcolo Network Health Score & Breakdown Dettagliato (Issue #15)
            health_details = self.calculate_health_details(network_details, eeros, enriched_devices)
            self.cached_health_score = health_details["score"]
            self.cached_health_details = health_details

            # 5. Aggiornamento Cache RAM
            if network_details:
                self.cached_network = _without_wifi_passwords(network_details)
            self.cached_eeros = eeros
            self.cached_devices = enriched_devices
            self.cached_profiles = profiles
            self._last_successful_poll = datetime.now(timezone.utc)
            self._last_poll_time = self._last_successful_poll

            # 6. Sincronizzazione automatica Speed Test reale da eero Gateway
            sp = network_details.get("speedtest") if isinstance(network_details, dict) else None
            if sp and isinstance(sp, dict) and sp.get("download_mbps"):
                down_val = round(float(sp["download_mbps"]), 2)
                up_val = round(float(sp.get("upload_mbps", 0)), 2)
                ping_val = round(float(sp.get("ping_ms", 0)), 1)
                
                is_mock_test = (
                    (abs(down_val - 912.45) < 0.05 and abs(up_val - 298.10) < 0.05) or
                    (abs(down_val - 2240.50) < 0.05 and abs(up_val - 980.20) < 0.05) or
                    down_val > 2000.0 or
                    "TIM FTTH" in str(network_details.get("isp", "")) or
                    "Fastweb FTTH" in str(network_details.get("isp", "")) or
                    "Fastweb" in str(network_details.get("isp", "")) or
                    getattr(eero_client, "is_demo_mode", False) or
                    (getattr(eero_client, "user_token", "") or "").startswith("demo_") or
                    str(network_details.get("id", "")).startswith("network_demo_")
                )
                if is_mock_test:
                    # Discard mock/demo speedtest telemetry leaking into SQLite database
                    should_save = False
                else:
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

            # 7. Arricchimento speedtest in cached_network con metriche Bufferbloat da SQLite
            if self.cached_network:
                sp_cached = self.cached_network.get("speedtest")
                if not isinstance(sp_cached, dict) or not sp_cached.get("bufferbloat_grade"):
                    try:
                        latest_db_tests = await db_service.get_speedtests(limit=1)
                        if latest_db_tests and len(latest_db_tests) > 0:
                            l_st = latest_db_tests[0]
                            if not isinstance(sp_cached, dict):
                                self.cached_network["speedtest"] = {}
                                sp_cached = self.cached_network["speedtest"]
                            if l_st.get("bufferbloat_grade"):
                                sp_cached["bufferbloat_grade"] = l_st["bufferbloat_grade"]
                            if l_st.get("bufferbloat_delta_ms") is not None:
                                sp_cached["bufferbloat_delta_ms"] = l_st["bufferbloat_delta_ms"]
                            if l_st.get("ping_under_load") is not None:
                                sp_cached["ping_under_load"] = l_st["ping_under_load"]
                            if not sp_cached.get("ping_ms") and l_st.get("ping_ms"):
                                sp_cached["ping_ms"] = l_st["ping_ms"]
                            if not sp_cached.get("download_mbps") and l_st.get("download_mbps"):
                                sp_cached["download_mbps"] = l_st["download_mbps"]
                            if not sp_cached.get("upload_mbps") and l_st.get("upload_mbps"):
                                sp_cached["upload_mbps"] = l_st["upload_mbps"]
                    except Exception as e:
                        logger.debug(f"Arricchimento bufferbloat cache network: {e}")

        except Exception as e:
            logger.error(f"Errore durante il salvataggio delle metriche di rete: {e}")

    @staticmethod
    def _get_local_now(tz_name: Optional[str] = None) -> datetime:
        """Restituisce il datetime corrente nel fuso orario configurato (default da settings.tz o env TZ),
        con fallback sicuro al fuso locale di sistema o UTC.
        """
        tz_str = (tz_name or getattr(settings, "tz", "") or os.getenv("TZ", "") or "").strip()
        if tz_str:
            if tz_str.upper() == "UTC":
                return datetime.now(timezone.utc)
            try:
                return datetime.now(zoneinfo.ZoneInfo(tz_str))
            except Exception:
                pass
        try:
            return datetime.now().astimezone()
        except Exception:
            return datetime.now()

    async def _run_periodic_jobs(self):
        """Esecuzione scheduler notturno LED, pulizia retention, speedtest e daily digest."""
        now = datetime.now()
        local_now = self._get_local_now()
        
        # A. Scheduler Modalità Notte LED (rispetta il fuso locale)
        night_mode_enabled = (await db_service.get_setting("night_mode_enabled", "false")).lower() == "true"
        if night_mode_enabled:
            start_str = await db_service.get_setting("night_mode_start", "23:00")
            end_str = await db_service.get_setting("night_mode_end", "07:00")
            try:
                sh, sm = map(int, start_str.split(":"))
                eh, em = map(int, end_str.split(":"))
                start_time = dt_time(sh, sm)
                end_time = dt_time(eh, em)
                curr_time = local_now.time()

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
                async def _safe_scheduled_speedtest():
                    try:
                        await speedtest_service.run_speedtest()
                    except Exception as err:
                        logger.warning(f"Scheduled speedtest failed: {err}")
                asyncio.create_task(_safe_scheduled_speedtest())

        # D. Daily Digest (persistenza su DB SQLite per evitare re-invii continui e spam dopo riavvii del container - Issue #70)
        configured_hour = int(await db_service.get_setting("daily_digest_hour", str(getattr(settings, "daily_digest_hour", 21))))
        today_str = local_now.strftime("%Y-%m-%d")
        if local_now.hour == configured_hour:
            last_digest_date = await db_service.get_setting("last_daily_digest_date", "")
            if last_digest_date != today_str and self._last_digest_date != today_str:
                self._last_digest_date = today_str
                await db_service.set_setting("last_daily_digest_date", today_str)
                digest_enabled = (await db_service.get_setting("daily_digest_enabled", "true")).lower() == "true"
                if digest_enabled:
                    asyncio.create_task(self._send_daily_digest())
                else:
                    logger.debug("Daily digest automatic dispatch is disabled in settings.")
            else:
                logger.debug(f"Daily digest for {today_str} already recorded as sent. Skipping.")

        # E. Sincronizzazione periodica AdGuard Home (ogni 30 minuti)
        if self.cached_devices and (not self._last_adguard_sync or (now - self._last_adguard_sync).total_seconds() > 1800):
            self._last_adguard_sync = now
            asyncio.create_task(adguard_service.auto_sync_if_enabled(self.cached_devices))

        # F. Sincronizzazione periodica Note di Rilascio eeroOS (ogni 6 ore)
        if not self._last_eero_news_run or (now - self._last_eero_news_run).total_seconds() > 21600:
            self._last_eero_news_run = now
            async def _safe_news_refresh():
                try:
                    from app.services.eero_news_service import eero_news_service
                    await eero_news_service.fetch_official_release_notes()
                except Exception as err:
                    logger.debug(f"Periodic eero release notes refresh skipped/failed: {err}")
            asyncio.create_task(_safe_news_refresh())

        # G. Parental Scheduling & Regole Temporali (v1.6.0 Modulo 1)
        try:
            from app.services.scheduler import schedule_engine
            asyncio.create_task(schedule_engine.evaluate_schedules(local_now))
        except Exception as sch_err:
            logger.debug(f"Periodic schedule evaluation error: {sch_err}")

        # H. Manutenzione Notturna Mesh & Compattazione SQLite (v1.6.0 Modulo 1)
        try:
            from app.services.scheduler import maintenance_engine
            asyncio.create_task(maintenance_engine.check_and_run_nightly_maintenance(local_now))
        except Exception as maint_err:
            logger.debug(f"Periodic maintenance check error: {maint_err}")

    async def _send_daily_digest(self, lang: Optional[str] = None) -> Dict[str, Any]:
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
            online_nodes = sum(1 for e in self.cached_eeros if e.get("status") in ("online", "green"))
            
            # Informazioni WAN e Speedtest Gateway
            net = self.cached_network or {}
            wan_down = net.get("speed_down_mbps") or stats.get("avg_download") or 0.0
            wan_up = net.get("speed_up_mbps") or stats.get("avg_upload") or 0.0
            wan_ping = net.get("ping_ms") or stats.get("avg_ping") or 0.0
            isp_name = net.get("isp") or tr("notifications.not_available", lang=lang)
            network_name = net.get("name") or tr("notifications.default_network_name", lang=lang)
            health_score = self.cached_health_score or 100

            digest_payload = {
                "network_name": network_name,
                "health_score": health_score,
                "line_stability": health_score,
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
            await notification_service.notify_digest(digest_payload, lang=lang)
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
poller = background_poller
