import asyncio
import logging
from datetime import datetime, timezone, time as dt_time
from typing import Any, Dict, List, Optional, Set

from app.config import settings
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
        self._known_eeros_status: Dict[str, str] = {}
        self._last_night_mode_state: Optional[bool] = None
        self._last_retention_run: Optional[datetime] = None
        self._last_scheduled_speedtest: Optional[datetime] = None
        self._last_digest_date: Optional[str] = None
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
            device_to_profile: Dict[str, Dict[str, Any]] = {}
            for prof in profiles:
                p_id = prof.get("id")
                p_name = prof.get("name")
                for p_dev in prof.get("devices", []):
                    p_mac = (p_dev.get("mac") or "").lower()
                    p_dev_id = str(p_dev.get("id") or "")
                    if p_mac:
                        device_to_profile[p_mac] = {"profile_id": p_id, "profile_name": p_name}
                    if p_dev_id:
                        device_to_profile[p_dev_id] = {"profile_id": p_id, "profile_name": p_name}

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

            for dev in devices:
                mac = (dev.get("mac") or dev.get("mac_address") or "").lower()
                dev_id_str = str(dev.get("id") or "")
                meta = metadata_map.get(mac, {})
                cloud_res_ip = cloud_reservations.get(mac)
                static_ip_val = cloud_res_ip or meta.get("static_ip", "")
                is_static = bool(cloud_res_ip or meta.get("static_ip") or dev.get("is_static"))
                
                # Profilo utente associato
                prof_info = device_to_profile.get(mac) or device_to_profile.get(dev_id_str) or {}
                
                dev_copy = dict(dev)
                dev_copy["mac"] = mac
                dev_copy["custom_name"] = meta.get("custom_name") or dev.get("nickname") or dev.get("hostname")
                dev_copy["custom_icon"] = meta.get("custom_icon", "device")
                dev_copy["category"] = meta.get("category", "Altro")
                dev_copy["custom_notes"] = meta.get("custom_notes", "")
                dev_copy["static_ip"] = static_ip_val
                dev_copy["is_static"] = is_static
                dev_copy["is_favorite"] = bool(meta.get("is_favorite", False))
                dev_copy["is_low_latency_target"] = bool(meta.get("is_low_latency_target", False))
                dev_copy["profile_id"] = prof_info.get("profile_id")
                dev_copy["profile_name"] = prof_info.get("profile_name")
                enriched_devices.append(dev_copy)

                # Rilevamento nuovo dispositivo
                if mac and self._known_macs and mac not in self._known_macs:
                    self._known_macs.add(mac)
                    asyncio.create_task(notification_service.notify_new_device(dev_copy))
                elif mac:
                    self._known_macs.add(mac)

            # 3. Distribuzione conteggio client connessi per singolo nodo eero
            for node in eeros:
                node_id = str(node.get("id") or node.get("serial") or "")
                node_name = str(node.get("name") or node.get("location") or "")
                matched_clients = [
                    d for d in enriched_devices
                    if d.get("connected") and (
                        str(d.get("connected_eero_id", "")) == node_id or
                        str(d.get("connected_eero_name", "")).lower() == node_name.lower() or
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
            asyncio.create_task(self._send_daily_digest())

    async def _send_daily_digest(self):
        try:
            hogs = await db_service.get_top_bandwidth_hogs(hours=24, limit=1)
            stats = await db_service.get_speedtest_stats()
            wan_hist = await db_service.get_wan_metrics_history(hours=24)
            
            total_gb = 0.0
            if wan_hist and len(wan_hist) > 1:
                total_rx = wan_hist[-1].get("rx_bytes", 0) - wan_hist[0].get("rx_bytes", 0)
                total_tx = wan_hist[-1].get("tx_bytes", 0) - wan_hist[0].get("tx_bytes", 0)
                total_gb = round(max(0, total_rx + total_tx) / (1024 ** 3), 2)

            top_dev_name = hogs[0].get("display_name", "N/D") if hogs else "N/D"
            top_dev_gb = round(hogs[0].get("total_bytes", 0) / (1024 ** 3), 2) if hogs else 0

            digest_payload = {
                "total_gb": total_gb,
                "top_device": top_dev_name,
                "top_device_gb": top_dev_gb,
                "avg_down_mbps": stats.get("avg_download", 0),
                "avg_up_mbps": stats.get("avg_upload", 0),
                "avg_ping_ms": stats.get("avg_ping", 0),
                "active_devices_count": len([d for d in self.cached_devices if d.get("connected")]),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await notification_service.notify_digest(digest_payload)
        except Exception as e:
            logger.error(f"Errore invio digest giornaliero: {e}")


# Istanza singleton background poller
background_poller = BackgroundPoller()
