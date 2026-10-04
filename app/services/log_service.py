"""
Log Service & SQLite Handler (v1.6.0 Module 4)

Fornisce la gestione centralizzata dei log di sistema:
- Handler per file rotativo (data/system.log) con rotazione per dimensione (max 10MB)
- SQLiteLogHandler asincrono con buffer in-memory per indicizzazione e ricerca avanzata
- Riconfigurazione a caldo di livello di dettaglio (DEBUG, INFO, WARNING, ERROR) e stato ON/OFF
- Svuotamento ed esportazione sicura dei file di log
"""

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import traceback
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.db import db_service

logger = logging.getLogger(__name__)

# Livelli di log supportati
VALID_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class SQLiteLogHandler(logging.Handler):
    """
    Handler logging non-bloccante che accumula record in un buffer in memoria
    e li persiste asincronamente nella tabella system_logs di SQLite.
    """

    # Namespace esclusi per prevenire ricorsioni o rumore interno di aiosqlite
    IGNORED_LOGGERS = {
        "app.services.db",
        "app.services.log_service",
        "aiosqlite",
        "asyncio",
        "urllib3",
    }

    def __init__(self, max_buffer_size: int = 5000):
        super().__init__()
        self._buffer: deque = deque(maxlen=max_buffer_size)
        self._enabled: bool = True
        self._lock = asyncio.Lock()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def emit(self, record: logging.LogRecord):
        if not self._enabled:
            return

        # Prevenzione loop di logging ricorsivo
        if any(record.name.startswith(ignored) for ignored in self.IGNORED_LOGGERS):
            return

        try:
            # Estrazione timestamp UTC
            ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            msg = record.getMessage()

            details_json = None
            if record.exc_info:
                exc_text = "".join(traceback.format_exception(*record.exc_info))
                details_json = json.dumps({"exc_info": exc_text})

            self._buffer.append({
                "timestamp": ts,
                "level": record.levelname,
                "logger_name": record.name,
                "message": msg,
                "details_json": details_json,
            })
        except Exception:
            self.handleError(record)

    async def flush_to_db(self) -> int:
        """Svuota il buffer in memoria e scrive i record nella tabella SQLite."""
        if not self._buffer:
            return 0

        batch: List[Dict[str, Any]] = []
        # Preleva fino a 200 record alla volta per batching efficiente
        while self._buffer and len(batch) < 200:
            try:
                batch.append(self._buffer.popleft())
            except IndexError:
                break

        if not batch:
            return 0

        try:
            return await db_service.insert_system_logs_batch(batch)
        except Exception as e:
            # In caso di errore temporaneo di scrittura DB, non perdere i record
            # li reinseriamo in testa al buffer se c'è spazio
            for item in reversed(batch):
                self._buffer.appendleft(item)
            return 0

    def clear_buffer(self):
        """Azzera il buffer in memoria."""
        self._buffer.clear()


class LogService:
    """
    Servizio di gestione globale del logging runtime:
    - Inizializzazione e wiring con il root logger
    - Gestione file system.log e tabella SQLite
    - Reconfig a caldo senza riavvio dell'applicazione
    """

    def __init__(self):
        self.sqlite_handler = SQLiteLogHandler()
        self.file_handler: Optional[RotatingFileHandler] = None
        self._flusher_task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._current_level: str = "INFO"
        self._enabled: bool = True

    @property
    def log_file_path(self) -> Path:
        return settings.log_file_path

    async def start(self):
        """Inizializza i logger, carica le impostazioni da DB e avvia il flusher in background."""
        if self._running:
            return

        # 1. Carica configurazione persistente da SQLite
        cfg = await db_service.get_logging_config()
        self._enabled = cfg.get("enabled", True)
        self._current_level = cfg.get("level", "INFO")

        # 2. Configura il File Handler rotativo
        log_path = self.log_file_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=3,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.file_handler.setFormatter(formatter)

        # 3. Imposta i livelli iniziali
        lvl_num = VALID_LOG_LEVELS.get(self._current_level, logging.INFO)
        self.sqlite_handler.setLevel(lvl_num)
        self.sqlite_handler.set_enabled(self._enabled)
        self.file_handler.setLevel(lvl_num)

        # 4. Aggancia gli handler al root logger e a eero_dashboard
        root_logger = logging.getLogger()
        if self.file_handler not in root_logger.handlers:
            root_logger.addHandler(self.file_handler)
        if self.sqlite_handler not in root_logger.handlers:
            root_logger.addHandler(self.sqlite_handler)

        eero_logger = logging.getLogger("eero_dashboard")
        eero_logger.setLevel(lvl_num)

        # 5. Avvia loop asincrono di flush del buffer SQLite
        self._running = True
        self._flusher_task = asyncio.create_task(self._flusher_loop())
        logger.info(
            f"LogService avviato con successo. Livello: {self._current_level}, "
            f"Abilitato: {self._enabled}, File: {self.log_file_path}"
        )

    async def stop(self):
        """Arresta il flusher in background e chiude i file."""
        self._running = False
        if self._flusher_task and not self._flusher_task.done():
            self._flusher_task.cancel()
            try:
                await self._flusher_task
            except asyncio.CancelledError:
                pass

        # Flush finale
        await self.sqlite_handler.flush_to_db()

        # Rimuovi handler
        root_logger = logging.getLogger()
        if self.file_handler in root_logger.handlers:
            root_logger.removeHandler(self.file_handler)
            self.file_handler.close()
        if self.sqlite_handler in root_logger.handlers:
            root_logger.removeHandler(self.sqlite_handler)

        logger.info("LogService arrestato correttamente.")

    async def _flusher_loop(self):
        """Loop asincrono che svuota il buffer di log in SQLite ogni secondo."""
        while self._running:
            try:
                await self.sqlite_handler.flush_to_db()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Evita crash del flusher
                pass
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break

    async def set_level(self, level_name: str) -> str:
        """Modifica a caldo il livello di logging per l'intera applicazione."""
        lvl_clean = level_name.upper().strip()
        if lvl_clean not in VALID_LOG_LEVELS:
            raise ValueError(f"Livello log non valido: {level_name}. Ammessi: {list(VALID_LOG_LEVELS.keys())}")

        lvl_num = VALID_LOG_LEVELS[lvl_clean]
        self._current_level = lvl_clean

        # Aggiorna handler
        self.sqlite_handler.setLevel(lvl_num)
        if self.file_handler:
            self.file_handler.setLevel(lvl_num)

        # Aggiorna logger
        logging.getLogger().setLevel(lvl_num)
        logging.getLogger("eero_dashboard").setLevel(lvl_num)

        # Salva configurazione persistente
        await db_service.set_logging_config(level=lvl_clean)
        logger.info(f"Livello di logging aggiornato a caldo a: {lvl_clean}")
        return self._current_level

    async def set_enabled(self, enabled: bool) -> bool:
        """Attiva o disattiva il logging a caldo."""
        self._enabled = enabled
        self.sqlite_handler.set_enabled(enabled)

        # Se disabilitato, il file handler viene impostato a un livello inarrivabile o disabilitato
        if self.file_handler:
            if not enabled:
                self.file_handler.setLevel(logging.CRITICAL + 1)
            else:
                lvl_num = VALID_LOG_LEVELS.get(self._current_level, logging.INFO)
                self.file_handler.setLevel(lvl_num)

        await db_service.set_logging_config(enabled=enabled)
        logger.info(f"Stato logging aggiornato a caldo: {'ATTIVO' if enabled else 'DISATTIVATO'}")
        return self._enabled

    async def set_retention_days(self, days: int) -> int:
        """Imposta il periodo di conservazione dei log in giorni."""
        d = max(0, int(days))
        await db_service.set_logging_config(retention_days=d)
        logger.info(f"Retention dei log aggiornata a: {d} giorni")
        return d

    async def clear_logs(self) -> Dict[str, Any]:
        """Svuota istantaneamente sia la tabella SQLite che il file fisico system.log."""
        # 1. Svuota buffer in memoria
        self.sqlite_handler.clear_buffer()

        # 2. Svuota tabella SQLite
        deleted_rows = await db_service.clear_system_logs()

        # 3. Tronca il file fisico
        try:
            if self.file_handler:
                self.file_handler.flush()
            log_p = self.log_file_path
            if log_p.exists():
                with open(log_p, "w", encoding="utf-8") as f:
                    f.truncate(0)
        except Exception as e:
            logger.warning(f"Errore durante lo svuotamento del file di log: {e}")

        # Inserisci una riga iniziale pulita di audit
        ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        await db_service.insert_system_log(
            level="INFO",
            logger_name="app.services.log_service",
            message=f"Log di sistema cancellati con successo (rimossi {deleted_rows} record precedenti).",
            timestamp=ts_now,
        )

        return {
            "status": "success",
            "deleted_records": deleted_rows,
            "timestamp": ts_now,
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Recupera statistiche aggregate sui log."""
        db_stats = await db_service.get_system_logs_stats()
        cfg = await db_service.get_logging_config()
        return {
            "config": cfg,
            "stats": db_stats,
            "buffer_pending": len(self.sqlite_handler._buffer),
        }


# Istanza singleton globale
log_service = LogService()
