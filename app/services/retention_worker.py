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
        logger.info("RetentionWorker: Motore asincrono di compattazione e tiering avviato.")

    async def stop(self):
        """Arresta il task di background."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("RetentionWorker: Motore di compattazione arrestato.")

    async def _worker_loop(self):
        """Loop asincrono periodico di tiering e compattazione."""
        # Breve attesa iniziale per consentire il bootstrap del server e il primo poll
        await asyncio.sleep(45)

        while self._running:
            try:
                logger.info("RetentionWorker: Avvio ciclo periodico di compattazione e tiering...")
                summary = await self.run_compaction_cycle()
                logger.info(
                    f"RetentionWorker: Ciclo completato con successo. "
                    f"Ore aggregate: {summary.get('hours_aggregated', 0)}, "
                    f"Giorni aggregati: {summary.get('days_aggregated', 0)}, "
                    f"Grezzi eliminati: {summary.get('raw_purged', {})}"
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"RetentionWorker: Errore imprevisto durante il ciclo di compattazione: {e}", exc_info=True)

            interval_minutes = getattr(settings, "retention_worker_interval_minutes", 60)
            sleep_seconds = max(300, interval_minutes * 60)
            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                break

    async def run_compaction_cycle(self) -> Dict[str, Any]:
        """
        Esegue un ciclo completo e atomico di tiering:
        1. Trova le ore concluse non ancora aggregate e genera i record hourly.
        2. Trova i giorni conclusi e genera i record daily.
        3. Elimina i campioni scaduti (Tier 1 > 48h, Tier 2 > 30d, Tier 3 > 365d).
        4. Esegue PRAGMA optimize sul database SQLite.
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            current_hour = now.replace(minute=0, second=0, microsecond=0)
            current_day = now.date()

            hours_aggregated = 0
            signals_aggregated = 0
            days_aggregated = 0

            # 1. Rileva ore concluse da aggregare (negli ultimi 7 giorni)
            cutoff_history = current_hour - timedelta(days=7)
            cutoff_history_str = cutoff_history.strftime("%Y-%m-%d %H:%M:%S")
            current_hour_str = current_hour.strftime("%Y-%m-%d %H:%M:%S")

            pending_hours = set()
            async with db_service.get_connection() as db:
                # Trova ore presenti nei campioni grezzi
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
                    if r["h"]:
                        pending_hours.add(r["h"])

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
                    if r["h"]:
                        pending_hours.add(r["h"])

            # Esegui aggregazione oraria per ogni ora conclusa trovata
            for h_str in sorted(pending_hours):
                try:
                    h_dt = datetime.strptime(h_str, "%Y-%m-%d %H:00:00").replace(tzinfo=timezone.utc)
                    u_cnt = await db_service.aggregate_hourly_usage(h_dt)
                    s_cnt = await db_service.aggregate_hourly_signals(h_dt)
                    if u_cnt > 0:
                        hours_aggregated += 1
                    if s_cnt > 0:
                        signals_aggregated += 1
                except Exception as ex:
                    logger.warning(f"RetentionWorker: Errore aggregazione ora {h_str}: {ex}")

            # 2. Rileva giorni conclusi da aggregare (negli ultimi 30 giorni)
            pending_days = set()
            async with db_service.get_connection() as db:
                cur_d = await db.execute(
                    """
                    SELECT DISTINCT date(hour_timestamp) as d
                    FROM device_usage_hourly
                    WHERE hour_timestamp < ?
                    """,
                    (current_day.strftime("%Y-%m-%d"),)
                )
                rows_d = await cur_d.fetchall()
                for r in rows_d:
                    if r["d"]:
                        pending_days.add(r["d"])

            for d_str in sorted(pending_days):
                try:
                    d_cnt = await db_service.aggregate_daily_usage(d_str)
                    if d_cnt > 0:
                        days_aggregated += 1
                except Exception as ex:
                    logger.warning(f"RetentionWorker: Errore aggregazione giorno {d_str}: {ex}")

            # 3. Purga dei dati scaduti per ciascun Tier
            raw_purged = await db_service.purge_expired_raw_samples()
            hourly_purged = await db_service.purge_expired_hourly_samples()
            daily_purged = await db_service.purge_expired_daily_samples()

            # 4. Ottimizzazione SQLite WAL & statistiche
            await db_service.run_database_maintenance(vacuum=False)
            db_stats = await db_service.get_database_stats()

            self._last_run = now
            self._last_summary = {
                "status": "success",
                "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "hours_aggregated": hours_aggregated,
                "signals_aggregated": signals_aggregated,
                "days_aggregated": days_aggregated,
                "raw_purged": raw_purged,
                "hourly_purged": hourly_purged,
                "daily_purged": daily_purged,
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
