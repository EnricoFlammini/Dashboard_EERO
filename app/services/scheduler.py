"""
Engine di pianificazione oraria (Parental Scheduling) e Manutenzione Notturna Mesh (v1.6.0 Modulo 1).
Gestisce regole temporali di pausa connettività su apparati e profili,
con supporto a finestre notturne a cavallo di mezzanotte e routine di auto-guarigione mesh.
"""

import asyncio
import json
import logging
from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from app.services.db import db_service
from app.services.eero_client import eero_client
from app.services.notifications import notification_service

logger = logging.getLogger(__name__)

DAY_NAME_MAP = {
    "mon": 0, "monday": 0, "lun": 0, "lunedi": 0, "lunedì": 0,
    "tue": 1, "tuesday": 1, "mar": 1, "martedi": 1, "martedì": 1,
    "wed": 2, "wednesday": 2, "mer": 2, "mercoledi": 2, "mercoledì": 2,
    "thu": 3, "thursday": 3, "gio": 3, "giovedi": 3, "giovedì": 3,
    "fri": 4, "friday": 4, "ven": 4, "venerdi": 4, "venerdì": 4,
    "sat": 5, "saturday": 5, "sab": 5, "sabato": 5,
    "sun": 6, "sunday": 6, "dom": 6, "domenica": 6,
}


def parse_time_str(val: str, default: dt_time = dt_time(0, 0)) -> dt_time:
    """Estrae un oggetto time da stringa HH:MM."""
    try:
        parts = str(val).strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return dt_time(h, m)
    except Exception:
        return default


class ScheduleEngine:
    """
    Motore di valutazione ed esecuzione delle regole di Parental Scheduling.
    Intercetta le transizioni temporali e applica la pausa/riattivazione su dispositivi o profili.
    """

    def __init__(self):
        # Mappa schedule_id -> stato attivo nell'ultimo ciclo (True/False)
        self._active_states: Dict[int, bool] = {}

    @staticmethod
    def is_schedule_active_at(schedule: Dict[str, Any], dt: datetime) -> bool:
        """
        Determina con precisione se una regola è attiva al momento specificato.
        Gestisce correttamente le finestre notturne a cavallo della mezzanotte (es. 22:00 -> 07:00).
        """
        if not schedule.get("enabled", True):
            return False

        start_t = parse_time_str(schedule.get("start_time", "22:00"))
        end_t = parse_time_str(schedule.get("end_time", "07:00"))
        curr_t = dt.time()

        days_raw = schedule.get("days_of_week") or []
        if isinstance(days_raw, str):
            try:
                days_raw = json.loads(days_raw)
            except Exception:
                days_raw = [d.strip() for d in days_raw.split(",") if d.strip()]

        # Se nessun giorno specificato, la regola si intende per tutti i giorni
        if not days_raw:
            schedule_day_indices = set(range(7))
        else:
            schedule_day_indices = set()
            for d in days_raw:
                d_str = str(d).lower().strip()
                if d_str in DAY_NAME_MAP:
                    schedule_day_indices.add(DAY_NAME_MAP[d_str])
                elif d_str.isdigit() and 0 <= int(d_str) <= 6:
                    schedule_day_indices.add(int(d_str))

        curr_weekday = dt.weekday()  # 0=Monday, 6=Sunday
        prev_weekday = (curr_weekday - 1) % 7

        is_today_scheduled = curr_weekday in schedule_day_indices
        is_yesterday_scheduled = prev_weekday in schedule_day_indices

        # Caso A: Finestra diurna nello stesso giorno (es. 08:00 -> 18:00)
        if start_t <= end_t:
            return is_today_scheduled and (start_t <= curr_t < end_t)

        # Caso B: Finestra notturna a cavallo di mezzanotte (es. 22:00 -> 07:00)
        if curr_t >= start_t:
            # Siamo nella prima metà della notte (prima di mezzanotte)
            return is_today_scheduled
        elif curr_t < end_t:
            # Siamo nella seconda metà della notte (dopo mezzanotte)
            # La regola è attiva solo se ieri sera era uno dei giorni pianificati
            return is_yesterday_scheduled
        else:
            return False

    async def evaluate_schedules(self, current_dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Valuta tutte le regole attive e applica le transizioni di stato (pausa o ripristino).
        """
        now = current_dt or datetime.now()
        schedules = await db_service.get_device_schedules(only_enabled=True)

        evaluated = []
        applied_actions = []

        for s in schedules:
            s_id = int(s["id"])
            s_name = s.get("name", f"Regola #{s_id}")
            t_type = s.get("target_type", "devices")
            targets = s.get("target_ids") or []
            action = s.get("action", "pause")

            is_active_now = self.is_schedule_active_at(s, now)
            prev_active = self._active_states.get(s_id)

            evaluated.append({
                "id": s_id,
                "name": s_name,
                "is_active": is_active_now,
                "prev_active": prev_active,
                "transition": (prev_active is not None and prev_active != is_active_now)
            })

            # Rilevamento transizione di stato
            if prev_active is None or prev_active != is_active_now:
                self._active_states[s_id] = is_active_now
                should_pause = (action == "pause" and is_active_now)

                logger.info(
                    f"ScheduleEngine: Transizione regola #{s_id} '{s_name}' -> "
                    f"{'ATTIVA (Pausa Internet)' if is_active_now else 'DISATTIVA (Ripristino Internet)'}"
                )

                if t_type == "profile":
                    for prof_id in targets:
                        try:
                            await eero_client.set_profile_paused(str(prof_id), should_pause)
                            applied_actions.append({"target": f"profile:{prof_id}", "paused": should_pause})
                        except Exception as ex:
                            logger.error(f"ScheduleEngine error pausing profile {prof_id}: {ex}")

                elif t_type in ("all_profiles", "all_users"):
                    try:
                        profs = await eero_client.get_profiles()
                        for p in profs:
                            p_id = str(p.get("id") or p.get("url", "").split("/")[-1])
                            await eero_client.set_profile_paused(p_id, should_pause)
                            applied_actions.append({"target": f"profile:{p_id}", "paused": should_pause})
                    except Exception as ex:
                        logger.error(f"ScheduleEngine error pausing all profiles: {ex}")

                elif t_type in ("node_led", "led"):
                    led_state = (not is_active_now) if action in ("turn_off", "off", "pause") else is_active_now
                    for node_id in targets:
                        try:
                            await eero_client.set_eero_led(str(node_id), led_on=led_state)
                            applied_actions.append({"target": f"node_led:{node_id}", "led_on": led_state})
                        except Exception as ex:
                            logger.error(f"ScheduleEngine error setting LED on node {node_id}: {ex}")

                elif t_type in ("all_nodes_led", "all_leds"):
                    led_state = (not is_active_now) if action in ("turn_off", "off", "pause") else is_active_now
                    try:
                        from app.services.poller import background_poller
                        cached = background_poller.get_cached_state()
                        eeros = cached.get("eeros", [])
                        for node in eeros:
                            n_id = str(node.get("id") or node.get("serial", ""))
                            await eero_client.set_eero_led(n_id, led_on=led_state)
                            applied_actions.append({"target": f"node_led:{n_id}", "led_on": led_state})
                    except Exception as ex:
                        logger.error(f"ScheduleEngine error setting LED on all nodes: {ex}")

                elif t_type in ("node_reboot", "all_nodes_reboot"):
                    if is_active_now:
                        if t_type == "all_nodes_reboot" or "all" in targets:
                            try:
                                await eero_client.reboot_network()
                                applied_actions.append({"target": "network", "rebooted": True})
                            except Exception as ex:
                                logger.error(f"ScheduleEngine error rebooting network: {ex}")
                        else:
                            for node_id in targets:
                                try:
                                    await eero_client.reboot_eero(str(node_id))
                                    applied_actions.append({"target": f"node:{node_id}", "rebooted": True})
                                except Exception as ex:
                                    logger.error(f"ScheduleEngine error rebooting node {node_id}: {ex}")

                else:
                    for dev_id in targets:
                        try:
                            await eero_client.update_device(str(dev_id), paused=should_pause)
                            applied_actions.append({"target": f"device:{dev_id}", "paused": should_pause})
                        except Exception as ex:
                            logger.error(f"ScheduleEngine error pausing device {dev_id}: {ex}")

                # Registra l'evento nello storico allarmi
                status_label = "Attivata" if is_active_now else "Terminata"
                await db_service.save_alert(
                    alert_type="schedule_transition",
                    title=f"🕒 Regola Pianificata '{s_name}'",
                    message=f"La regola oraria '{s_name}' è stata applicata: stato {status_label} su {len(targets) if targets else 1} target ({t_type})."
                )

        return {
            "timestamp": now.isoformat(),
            "evaluated_count": len(evaluated),
            "applied_count": len(applied_actions),
            "schedules": evaluated,
            "actions": applied_actions,
        }

    def reset_state(self):
        """Azzera la cache interna delle transizioni (utile per test unitari)."""
        self._active_states.clear()


class MaintenanceEngine:
    """
    Motore di manutenzione periodica notturna e compattazione database SQLite.
    Monitora degradamenti di stabilità o packet loss della mesh e, se configurato,
    avvia procedure controllate di auto-guarigione (safe reboot) ed ottimizzazione WAL.
    """

    def __init__(self):
        self._last_run_date: Optional[str] = None

    async def get_settings(self) -> Dict[str, Any]:
        """Recupera le impostazioni di manutenzione notturna da app_settings."""
        all_s = await db_service.get_all_settings()
        return {
            "enabled": all_s.get("nightly_maintenance_enabled", "false").lower() == "true",
            "time": all_s.get("nightly_maintenance_time", "04:00"),
            "auto_reboot": all_s.get("nightly_maintenance_auto_reboot", "false").lower() == "true",
            "reboot_threshold_score": int(all_s.get("nightly_maintenance_reboot_threshold_score", "50")),
            "vacuum": all_s.get("nightly_maintenance_vacuum", "false").lower() == "true",
            "last_run": all_s.get("last_nightly_maintenance_run"),
        }

    async def save_settings(
        self,
        enabled: bool,
        time: str = "04:00",
        auto_reboot: bool = False,
        reboot_threshold_score: int = 50,
        vacuum: bool = False,
    ) -> None:
        """Salva le impostazioni di manutenzione notturna."""
        await db_service.set_setting("nightly_maintenance_enabled", "true" if enabled else "false")
        await db_service.set_setting("nightly_maintenance_time", time.strip())
        await db_service.set_setting("nightly_maintenance_auto_reboot", "true" if auto_reboot else "false")
        await db_service.set_setting("nightly_maintenance_reboot_threshold_score", str(reboot_threshold_score))
        await db_service.set_setting("nightly_maintenance_vacuum", "true" if vacuum else "false")

    async def run_maintenance_now(self, force: bool = True) -> Dict[str, Any]:
        """Esegue immediatamente il ciclo di manutenzione e compattazione."""
        cfg = await self.get_settings()
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        logger.info("MaintenanceEngine: Avvio procedura di manutenzione...")

        # 1. Manutenzione e compattazione SQLite (PRAGMA optimize e VACUUM opzionale)
        db_res = await db_service.run_database_maintenance(vacuum=cfg.get("vacuum", False))

        # 2. Diagnostica stato di salute Mesh e valutazione riavvio
        from app.services.poller import background_poller
        cached_state = background_poller.get_cached_state()
        health_score = cached_state.get("health_score", 100)
        eeros = cached_state.get("eeros", [])

        reboot_triggered = False
        reboot_reason = None
        rebooted_items = []

        if cfg.get("auto_reboot") or force:
            threshold = cfg.get("reboot_threshold_score", 50)
            if health_score < threshold:
                # Trova i nodi beacon degradati o offline (escluso gateway se possibile)
                degraded_beacons = [
                    e for e in eeros
                    if not e.get("is_gateway") and (
                        e.get("status") in ("offline", "disconnected", "red") or
                        (isinstance(e.get("signal_rssi"), (int, float)) and e["signal_rssi"] < -82)
                    )
                ]

                if degraded_beacons:
                    for b in degraded_beacons:
                        b_id = str(b.get("id") or b.get("serial") or "")
                        b_name = b.get("name") or "Extender"
                        if b_id:
                            try:
                                await eero_client.reboot_eero(b_id)
                                rebooted_items.append(f"{b_name} ({b_id})")
                            except Exception as re:
                                logger.error(f"MaintenanceEngine: Error rebooting node {b_id}: {re}")
                    reboot_triggered = bool(rebooted_items)
                    reboot_reason = f"Health score critico ({health_score}/{threshold}) e {len(degraded_beacons)} nodi beacon degradati."
                else:
                    # Se l'intera rete è degradata, riavvio generale
                    try:
                        await eero_client.reboot_network()
                        reboot_triggered = True
                        reboot_reason = f"Health score generale critico ({health_score}/{threshold}). Riavvio preventivo rete."
                        rebooted_items.append("Rete eero Mesh Intera")
                    except Exception as re:
                        logger.error(f"MaintenanceEngine: Error rebooting network: {re}")

        # Salva log e invia notifica se è avvenuto un riavvio o se programmato
        if reboot_triggered:
            await db_service.save_alert(
                alert_type="nightly_maintenance_reboot",
                title="🔄 Manutenzione Notturna: Riavvio Mesh",
                message=f"{reboot_reason} Nodi riavviati: {', '.join(rebooted_items)}."
            )
            await notification_service.send_telegram_message(
                f"<b>🔄 Manutenzione Notturna eero</b>\n\n{reboot_reason}\nApparati: <code>{', '.join(rebooted_items)}</code>"
            )

        await db_service.set_setting("last_nightly_maintenance_run", now.isoformat())
        self._last_run_date = today_str

        return {
            "status": "success",
            "timestamp": now.isoformat(),
            "database_optimized": True,
            "health_score": health_score,
            "reboot_triggered": reboot_triggered,
            "reboot_reason": reboot_reason,
            "rebooted_items": rebooted_items,
            "sqlite": db_res,
        }

    async def check_and_run_nightly_maintenance(self, current_dt: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Controlla se l'orario corrente corrisponde alla finestra di manutenzione programmata."""
        now = current_dt or datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        cfg = await self.get_settings()
        if not cfg.get("enabled"):
            return None

        # Se già eseguito oggi, non rieseguire
        if self._last_run_date == today_str:
            return None

        target_t = parse_time_str(cfg.get("time", "04:00"))
        curr_t = now.time()

        # Esegui se siamo entro una finestra di 10 minuti dall'orario impostato
        if target_t.hour == curr_t.hour and abs(curr_t.minute - target_t.minute) <= 10:
            return await self.run_maintenance_now(force=False)

        return None


# Istanze singleton dei motori
schedule_engine = ScheduleEngine()
maintenance_engine = MaintenanceEngine()
