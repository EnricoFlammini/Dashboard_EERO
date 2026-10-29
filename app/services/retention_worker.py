"""
Retention Worker: Background Asynchronous Compaction & Tiering Engine (v1.6.0 Module 2)

Gestisce il ciclo di vita della memorizzazione dei dati delle serie temporali:
- Tier 1: Campioni grezzi (alta frequenza, conservati per 48 ore)
- Tier 2: Rollup orari (device_usage_hourly e device_signal_hourly, conservati per 30 giorni)
- Tier 3: Rollup giornalieri (device_usage_daily, conservati per 365 giorni)
- Ottimizzazione periodica degli indici SQLite e compattazione non bloccante.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.i18n import log_event
from app.services.db import db_service

logger = logging.getLogger(__name__)


class RetentionWorker:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._lock = asyncio.Lock()
        self._last_run: Optional[datetime] = None
        self._last_summary: Optional[Dict[str, Any]] = None

    async def start(self):
        """Avvia il task di background del retention worker."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._worker_loop())
        log_event(logger, logging.INFO, "log_ops.retention_started")

    async def stop(self):
        """Arresta il task di background."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log_event(logger, logging.INFO, "log_ops.retention_stopped")

    async def _worker_loop(self):
        """Loop asincrono periodico di tiering e compattazione."""
        # Breve attesa iniziale per consentire il bootstrap del server e il primo poll
        await asyncio.sleep(45)

        while self._running:
            try:
                log_event(logger, logging.INFO, "log_ops.retention_cycle_started")
                summary = await self.run_compaction_cycle()
                log_event(logger, logging.INFO, "log_ops.retention_cycle_completed",
                    hours=summary.get('hours_aggregated', 0),
                    days=summary.get('days_aggregated', 0),
                    raw_purged=summary.get('raw_purged', {}),
                    logs_purged=summary.get('logs_purged', 0),
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_event(logger, logging.ERROR, "log_ops.retention_cycle_failed", exc_info=True, error=str(e))

            interval_minutes = getattr(settings, "retention_worker_interval_minutes", 60)
            sleep_seconds = max(300, interval_minutes * 60)
            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                break

    async def run_compaction_cycle(self, vacuum: bool = False, force: bool = False) -> Dict[str, Any]:
        """
        Esegue un ciclo completo e atomico di tiering:
        1. Trova le ore concluse non ancora aggregate e genera i record hourly (saltando quelle già compattate se not force).
        2. Trova i giorni conclusi non ancora aggregati e genera i record daily.
        3. Elimina i campioni scaduti (Tier 1 > 48h, Tier 2 > 30d, Tier 3 > 365d) e log di sistema.
        4. Esegue PRAGMA optimize e WAL checkpoint sul database SQLite (e VACUUM se richiesto).
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            current_hour = now.replace(minute=0, second=0, microsecond=0)
            current_day = now.date()

            hours_aggregated = 0
            signals_aggregated = 0
            days_aggregated = 0
            errors = []

            # 1. Rileva ore concluse da aggregare (negli ultimi 7 giorni)
            cutoff_history = current_hour - timedelta(days=7)
            cutoff_history_str = cutoff_history.strftime("%Y-%m-%d %H:%M:%S")
            current_hour_str = current_hour.strftime("%Y-%m-%d %H:%M:%S")

            # Identifica le ore già aggregate in precedenza per saltarle se non forzato (Issue #73)
            done_hours_u = set()
            done_hours_s = set()
            if not force:
                async with db_service.get_connection() as db:
                    cur_u_done = await db.execute(
                        "SELECT DISTINCT hour_timestamp FROM device_usage_hourly WHERE hour_timestamp >= ? AND hour_timestamp < ?",
                        (cutoff_history_str, current_hour_str)
                    )
                    done_hours_u = {r["hour_timestamp"] for r in await cur_u_done.fetchall()}

                    cur_s_done = await db.execute(
                        "SELECT DISTINCT hour_timestamp FROM device_signal_hourly WHERE hour_timestamp >= ? AND hour_timestamp < ?",
                        (cutoff_history_str, current_hour_str)
                    )
                    done_hours_s = {r["hour_timestamp"] for r in await cur_s_done.fetchall()}

            pending_usage_hours = set()
            pending_signal_hours = set()
            async with db_service.get_connection() as db:
                # Trova ore presenti nei campioni grezzi usage
                cur = await db.execute(
                    """
                    SELECT DISTINCT strftime('%Y-%m-%d %H:00:00', replace(replace(timestamp, 'T', ' '), 'Z', '')) as h
                    FROM device_usage_history
                    WHERE replace(replace(timestamp, 'T', ' '), 'Z', '') >= ? 
                      AND replace(replace(timestamp, 'T', ' '), 'Z', '') < ?
                    """,
                    (cutoff_history_str, current_hour_str)
                )
                rows = await cur.fetchall()
                for r in rows:
                    if r["h"] and (force or r["h"] not in done_hours_u):
                        pending_usage_hours.add(r["h"])

                # Aggiungi ore presenti nei segnali grezzi
                cur_sig = await db.execute(
                    """
                    SELECT DISTINCT strftime('%Y-%m-%d %H:00:00', replace(replace(timestamp, 'T', ' '), 'Z', '')) as h
                    FROM device_signal_history
                    WHERE replace(replace(timestamp, 'T', ' '), 'Z', '') >= ? 
                      AND replace(replace(timestamp, 'T', ' '), 'Z', '') < ?
                    """,
                    (cutoff_history_str, current_hour_str)
                )
                rows_sig = await cur_sig.fetchall()
                for r in rows_sig:
                    if r["h"] and (force or r["h"] not in done_hours_s):
                        pending_signal_hours.add(r["h"])

            # Esegui aggregazione oraria solo per le ore effettivamente non aggregate
            all_target_hours = sorted(pending_usage_hours.union(pending_signal_hours))
            for h_str in all_target_hours:
                h_dt = datetime.strptime(h_str, "%Y-%m-%d %H:00:00").replace(tzinfo=timezone.utc)
                if h_str in pending_usage_hours:
                    try:
                        u_cnt = await db_service.aggregate_hourly_usage(h_dt)
                        if u_cnt > 0:
                            hours_aggregated += 1
                    except Exception as ex:
                        err_msg = f"RetentionWorker: Usage aggregation error for hour {h_str}: {ex}"
                        log_event(logger, logging.WARNING, "log_ops.retention_usage_hour_failed", hour=h_str, error=str(ex))
                        errors.append(err_msg)

                if h_str in pending_signal_hours:
                    try:
                        s_cnt = await db_service.aggregate_hourly_signals(h_dt)
                        if s_cnt > 0:
                            signals_aggregated += 1
                    except Exception as ex:
                        err_msg = f"RetentionWorker: Signal aggregation error for hour {h_str}: {ex}"
                        log_event(logger, logging.WARNING, "log_ops.retention_signals_hour_failed", hour=h_str, error=str(ex))
                        errors.append(err_msg)

            # 2. Rileva giorni conclusi da aggregare (negli ultimi 30 giorni)
            cutoff_days = current_day - timedelta(days=30)
            cutoff_day_str = cutoff_days.strftime("%Y-%m-%d")
            current_day_str = current_day.strftime("%Y-%m-%d")

            done_days = set()
            if not force:
                async with db_service.get_connection() as db:
                    cur_done_d = await db.execute(
                        "SELECT DISTINCT day_date FROM device_usage_daily WHERE day_date >= ? AND day_date < ?",
                        (cutoff_day_str, current_day_str)
                    )
                    done_days = {str(r["day_date"])[:10] for r in await cur_done_d.fetchall()}

            pending_days = set()
            async with db_service.get_connection() as db:
                cur_d = await db.execute(
                    """
                    SELECT DISTINCT date(hour_timestamp) as d
                    FROM device_usage_hourly
                    WHERE hour_timestamp >= ? AND hour_timestamp < ?
                    """,
                    (cutoff_day_str, current_day_str)
                )
                rows_d = await cur_d.fetchall()
                for r in rows_d:
                    d_val = str(r["d"])[:10] if r["d"] else ""
                    if d_val and (force or d_val not in done_days):
                        pending_days.add(d_val)

            for d_str in sorted(pending_days):
                try:
                    d_cnt = await db_service.aggregate_daily_usage(d_str)
                    if d_cnt > 0:
                        days_aggregated += 1
                except Exception as ex:
                    err_msg = f"RetentionWorker: Daily aggregation error for day {d_str}: {ex}"
                    log_event(logger, logging.WARNING, "log_ops.retention_day_failed", day=d_str, error=str(ex))
                    errors.append(err_msg)

            # 3. Purga dei dati scaduti per ciascun Tier e log di sistema
            raw_purged = await db_service.purge_expired_raw_samples()
            hourly_purged = await db_service.purge_expired_hourly_samples()
            daily_purged = await db_service.purge_expired_daily_samples()
            logs_purged = await db_service.purge_expired_system_logs()
            await db_service.cleanup_stale_discovered_ips(retention_days=7)

            # 4. Ottimizzazione SQLite WAL & statistiche
            maintenance_res = await db_service.run_database_maintenance(vacuum=vacuum)
            db_stats = await db_service.get_database_stats()

            self._last_run = now
            status = "success" if not errors else "warning"
            self._last_summary = {
                "status": status,
                "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "hours_aggregated": hours_aggregated,
                "signals_aggregated": signals_aggregated,
                "days_aggregated": days_aggregated,
                "raw_purged": raw_purged,
                "hourly_purged": hourly_purged,
                "daily_purged": daily_purged,
                "logs_purged": logs_purged,
                "errors": errors,
                "maintenance": maintenance_res,
                "db_stats": db_stats
            }
            return self._last_summary

    @property
    def last_summary(self) -> Optional[Dict[str, Any]]:
        return self._last_summary

    @property
    def last_run(self) -> Optional[datetime]:
        return self._last_run


# Singleton instance
retention_worker = RetentionWorker()
