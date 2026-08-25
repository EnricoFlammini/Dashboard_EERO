import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import aiosqlite
from app.config import settings

logger = logging.getLogger(__name__)


class DBService:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(settings.db_file_path)

    async def get_connection(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        return conn

    async def init_db(self):
        """Initialize database schema with tables and indexes."""
        logger.info(f"Initializing database at: {self.db_path}")
        async with await self.get_connection() as db:
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA synchronous = NORMAL;")
            
            # 1. WAN Metrics
            await db.execute("""
                CREATE TABLE IF NOT EXISTS wan_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    public_ip TEXT,
                    rx_bytes REAL DEFAULT 0,
                    tx_bytes REAL DEFAULT 0,
                    download_speed_mbps REAL DEFAULT 0,
                    upload_speed_mbps REAL DEFAULT 0
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_wan_metrics_time ON wan_metrics(timestamp);")

            # 2. Device Metrics
            await db.execute("""
                CREATE TABLE IF NOT EXISTS device_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    mac_address TEXT NOT NULL,
                    hostname TEXT,
                    rx_bytes REAL DEFAULT 0,
                    tx_bytes REAL DEFAULT 0,
                    download_rate REAL DEFAULT 0,
                    upload_rate REAL DEFAULT 0
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_dev_metrics_mac_time ON device_metrics(mac_address, timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_dev_metrics_time ON device_metrics(timestamp);")

            # 3. Speedtests
            await db.execute("""
                CREATE TABLE IF NOT EXISTS speedtests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    download_mbps REAL DEFAULT 0,
                    upload_mbps REAL DEFAULT 0,
                    ping_ms REAL DEFAULT 0,
                    jitter REAL DEFAULT 0,
                    server_name TEXT,
                    source TEXT DEFAULT 'eero_api'
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_speedtests_time ON speedtests(timestamp);")

            # 4. Device Metadata (Local annotations, custom icons, notes, static IP, etc.)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS device_metadata (
                    mac_address TEXT PRIMARY KEY,
                    custom_name TEXT,
                    custom_icon TEXT DEFAULT 'device',
                    category TEXT DEFAULT 'Altro',
                    custom_notes TEXT,
                    static_ip TEXT,
                    is_favorite INTEGER DEFAULT 0,
                    is_low_latency_target INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 5. App Settings (Key-Value store for automations, credentials, toggles)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 6. Alert & Audit History
            await db.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    type TEXT,
                    title TEXT,
                    message TEXT,
                    read INTEGER DEFAULT 0
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_time ON alert_history(timestamp);")

            # Inserimento impostazioni predefinite se assenti
            default_settings = [
                ("night_mode_enabled", "false"),
                ("night_mode_start", "23:00"),
                ("night_mode_end", "07:00"),
                ("focus_mode_active", "false"),
                ("focus_mode_paused_macs", "[]"),
                ("telegram_alerts_enabled", "true" if settings.telegram_bot_token else "false"),
                ("webhook_alerts_enabled", "true" if settings.webhook_url else "false"),
                ("history_retention_days", str(settings.history_retention_days)),
                ("poll_interval", str(settings.poll_interval)),
                ("speedtest_schedule_hours", str(settings.speedtest_interval_hours)),
            ]
            for key, val in default_settings:
                await db.execute(
                    "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?);",
                    (key, val)
                )

            await db.commit()
            logger.info("Database schema initialized successfully.")

    # ----------------- WAN METRICS -----------------
    async def save_wan_metrics(
        self,
        status: str,
        public_ip: str,
        rx_bytes: float,
        tx_bytes: float,
        download_speed_mbps: float,
        upload_speed_mbps: float,
    ) -> int:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with await self.get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO wan_metrics 
                (timestamp, status, public_ip, rx_bytes, tx_bytes, download_speed_mbps, upload_speed_mbps)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (now, status, public_ip, rx_bytes, tx_bytes, download_speed_mbps, upload_speed_mbps)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_wan_metrics_history(
        self,
        hours: Optional[int] = 24,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        async with await self.get_connection() as db:
            if start_time and end_time:
                query = """
                    SELECT timestamp, status, public_ip, rx_bytes, tx_bytes, 
                           download_speed_mbps, upload_speed_mbps 
                    FROM wan_metrics 
                    WHERE timestamp BETWEEN ? AND ? 
                    ORDER BY timestamp ASC
                """
                cursor = await db.execute(query, (start_time, end_time))
            else:
                hours = hours or 24
                since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
                query = """
                    SELECT timestamp, status, public_ip, rx_bytes, tx_bytes, 
                           download_speed_mbps, upload_speed_mbps 
                    FROM wan_metrics 
                    WHERE timestamp >= ? 
                    ORDER BY timestamp ASC
                """
                cursor = await db.execute(query, (since,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ----------------- DEVICE METRICS -----------------
    async def save_device_metrics_batch(self, metrics_list: List[Dict[str, Any]]):
        if not metrics_list:
            return
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        records = [
            (
                now,
                m.get("mac_address", ""),
                m.get("hostname", "Unknown"),
                float(m.get("rx_bytes", 0)),
                float(m.get("tx_bytes", 0)),
                float(m.get("download_rate", 0)),
                float(m.get("upload_rate", 0))
            )
            for m in metrics_list
        ]
        async with await self.get_connection() as db:
            await db.executemany(
                """
                INSERT INTO device_metrics 
                (timestamp, mac_address, hostname, rx_bytes, tx_bytes, download_rate, upload_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                records
            )
            await db.commit()

    async def get_device_metrics_history(self, mac_address: str, hours: int = 24) -> List[Dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        async with await self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT timestamp, mac_address, hostname, rx_bytes, tx_bytes, download_rate, upload_rate
                FROM device_metrics
                WHERE mac_address = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (mac_address, since)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_top_bandwidth_hogs(self, hours: int = 24, limit: int = 10) -> List[Dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        async with await self.get_connection() as db:
            # Calcoliamo il delta o l'aggregato di banda consumata nel periodo
            cursor = await db.execute(
                """
                SELECT 
                    dm.mac_address,
                    COALESCE(meta.custom_name, dm.hostname, dm.mac_address) as display_name,
                    COALESCE(meta.custom_icon, 'device') as custom_icon,
                    COALESCE(meta.category, 'Altro') as category,
                    MAX(dm.rx_bytes) - MIN(dm.rx_bytes) as total_rx_bytes,
                    MAX(dm.tx_bytes) - MIN(dm.tx_bytes) as total_tx_bytes,
                    (MAX(dm.rx_bytes) - MIN(dm.rx_bytes)) + (MAX(dm.tx_bytes) - MIN(dm.tx_bytes)) as total_bytes,
                    AVG(dm.download_rate) as avg_download_rate,
                    AVG(dm.upload_rate) as avg_upload_rate
                FROM device_metrics dm
                LEFT JOIN device_metadata meta ON dm.mac_address = meta.mac_address
                WHERE dm.timestamp >= ?
                GROUP BY dm.mac_address
                HAVING total_bytes > 0
                ORDER BY total_bytes DESC
                LIMIT ?
                """,
                (since, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ----------------- SPEEDTESTS -----------------
    async def save_speedtest(
        self,
        download_mbps: float,
        upload_mbps: float,
        ping_ms: float,
        jitter: float = 0.0,
        server_name: str = "eero Cloud SpeedTest",
        source: str = "eero_api"
    ) -> int:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with await self.get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO speedtests 
                (timestamp, download_mbps, upload_mbps, ping_ms, jitter, server_name, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (now, download_mbps, upload_mbps, ping_ms, jitter, server_name, source)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_speedtests(self, limit: int = 50) -> List[Dict[str, Any]]:
        async with await self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT id, timestamp, download_mbps, upload_mbps, ping_ms, jitter, server_name, source
                FROM speedtests
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_speedtest_stats(self) -> Dict[str, Any]:
        async with await self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT 
                    COUNT(*) as total_tests,
                    AVG(download_mbps) as avg_download,
                    MAX(download_mbps) as max_download,
                    AVG(upload_mbps) as avg_upload,
                    MAX(upload_mbps) as max_upload,
                    AVG(ping_ms) as avg_ping,
                    MIN(ping_ms) as min_ping
                FROM speedtests
                """
            )
            row = await cursor.fetchone()
            if row and row["total_tests"] > 0:
                return {
                    "total_tests": row["total_tests"],
                    "avg_download": round(row["avg_download"] or 0, 2),
                    "max_download": round(row["max_download"] or 0, 2),
                    "avg_upload": round(row["avg_upload"] or 0, 2),
                    "max_upload": round(row["max_upload"] or 0, 2),
                    "avg_ping": round(row["avg_ping"] or 0, 1),
                    "min_ping": round(row["min_ping"] or 0, 1),
                }
            return {
                "total_tests": 0,
                "avg_download": 0,
                "max_download": 0,
                "avg_upload": 0,
                "max_upload": 0,
                "avg_ping": 0,
                "min_ping": 0,
            }

    # ----------------- DEVICE METADATA -----------------
    async def get_all_device_metadata(self) -> Dict[str, Dict[str, Any]]:
        async with await self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM device_metadata")
            rows = await cursor.fetchall()
            return {row["mac_address"]: dict(row) for row in rows}

    async def get_device_metadata(self, mac_address: str) -> Optional[Dict[str, Any]]:
        async with await self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM device_metadata WHERE mac_address = ?", (mac_address,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def upsert_device_metadata(self, mac_address: str, **kwargs) -> Dict[str, Any]:
        existing = await self.get_device_metadata(mac_address)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if existing:
            updated = {**existing, **kwargs, "updated_at": now}
            async with await self.get_connection() as db:
                await db.execute(
                    """
                    UPDATE device_metadata
                    SET custom_name = ?, custom_icon = ?, category = ?, 
                        custom_notes = ?, static_ip = ?, is_favorite = ?, 
                        is_low_latency_target = ?, updated_at = ?
                    WHERE mac_address = ?
                    """,
                    (
                        updated.get("custom_name"),
                        updated.get("custom_icon", "device"),
                        updated.get("category", "Altro"),
                        updated.get("custom_notes"),
                        updated.get("static_ip"),
                        int(updated.get("is_favorite", 0)),
                        int(updated.get("is_low_latency_target", 0)),
                        now,
                        mac_address
                    )
                )
                await db.commit()
            return updated
        else:
            new_item = {
                "mac_address": mac_address,
                "custom_name": kwargs.get("custom_name"),
                "custom_icon": kwargs.get("custom_icon", "device"),
                "category": kwargs.get("category", "Altro"),
                "custom_notes": kwargs.get("custom_notes"),
                "static_ip": kwargs.get("static_ip"),
                "is_favorite": int(kwargs.get("is_favorite", 0)),
                "is_low_latency_target": int(kwargs.get("is_low_latency_target", 0)),
                "created_at": now,
                "updated_at": now,
            }
            async with await self.get_connection() as db:
                await db.execute(
                    """
                    INSERT INTO device_metadata 
                    (mac_address, custom_name, custom_icon, category, custom_notes, static_ip, is_favorite, is_low_latency_target, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_item["mac_address"],
                        new_item["custom_name"],
                        new_item["custom_icon"],
                        new_item["category"],
                        new_item["custom_notes"],
                        new_item["static_ip"],
                        new_item["is_favorite"],
                        new_item["is_low_latency_target"],
                        new_item["created_at"],
                        new_item["updated_at"]
                    )
                )
                await db.commit()
            return new_item

    # ----------------- APP SETTINGS -----------------
    async def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        async with await self.get_connection() as db:
            cursor = await db.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row["value"] if row else default

    async def set_setting(self, key: str, value: str):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with await self.get_connection() as db:
            await db.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, now)
            )
            await db.commit()

    async def get_all_settings(self) -> Dict[str, str]:
        async with await self.get_connection() as db:
            cursor = await db.execute("SELECT key, value FROM app_settings")
            rows = await cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}

    # ----------------- ALERTS & NOTIFICATIONS -----------------
    async def save_alert(self, alert_type: str, title: str, message: str) -> int:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with await self.get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO alert_history (timestamp, type, title, message, read)
                VALUES (?, ?, ?, ?, 0)
                """,
                (now, alert_type, title, message)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        async with await self.get_connection() as db:
            cursor = await db.execute(
                "SELECT id, timestamp, type, title, message, read FROM alert_history ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def mark_alerts_read(self):
        async with await self.get_connection() as db:
            await db.execute("UPDATE alert_history SET read = 1 WHERE read = 0")
            await db.commit()

    # ----------------- RETENTION CLEANUP -----------------
    async def cleanup_old_data(self, retention_days: Optional[int] = None) -> Dict[str, int]:
        days = retention_days or settings.history_retention_days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        deleted_counts = {}
        async with await self.get_connection() as db:
            c1 = await db.execute("DELETE FROM wan_metrics WHERE timestamp < ?", (cutoff,))
            deleted_counts["wan_metrics"] = c1.rowcount
            
            c2 = await db.execute("DELETE FROM device_metrics WHERE timestamp < ?", (cutoff,))
            deleted_counts["device_metrics"] = c2.rowcount
            
            c3 = await db.execute("DELETE FROM speedtests WHERE timestamp < ?", (cutoff,))
            deleted_counts["speedtests"] = c3.rowcount

            c4 = await db.execute("DELETE FROM alert_history WHERE timestamp < ?", (cutoff,))
            deleted_counts["alert_history"] = c4.rowcount

            await db.commit()
            logger.info(f"Data retention cleanup executed (cutoff: {cutoff}): {deleted_counts}")
        return deleted_counts


# Istanza singleton DB
db_service = DBService()
