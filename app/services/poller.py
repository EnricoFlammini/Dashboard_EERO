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
            "last_poll_time": self._last_poll_time.isoformat() if self._last_poll_time else None,
            "is_authenticated": eero_client.is_authenticated,
            "demo_mode": settings.demo_mode or (eero_client.user_token and eero_client.user_token.startswith("demo_")),
        }

    async def poll_once(self):
        """Esegue un ciclo di polling immediato e aggiorna la cache."""
        await self._poll_and_cache()

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
                    (r.get("mac") or "").lower(): r.get("ip") 
                    for r in forwards_res.get("reservations", [])
                    if r.get("mac")
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

            # Rilevamento nodi eero offline
            for node in eeros:
                node_id = str(node.get("id") or node.get("serial"))
                status = "online" if node.get("status") in ("online", "green") else "offline"
                if node_id in self._known_eeros_status:
                    prev_status = self._known_eeros_status[node_id]
                    if prev_status == "online" and status != "online":
                        asyncio.create_task(notification_service.notify_node_offline(node))
                self._known_eeros_status[node_id] = status

            # 4. Calcolo Network Health Score (1 - 100)
            health = 100
            offline_eeros = len([e for e in eeros if e.get("status") not in ("online", "green")])
            health -= offline_eeros * 25
            if network_details.get("status") not in ("online", "green"):
                health -= 50
            
            # Penalità per segnale debole sui client connessi
            weak_signals = len([d for d in enriched_devices if d.get("connected") and (d.get("signal_rssi") or 0) < -75])
            health -= min(weak_signals * 2, 15)
            self.cached_health_score = max(5, min(100, health))

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
