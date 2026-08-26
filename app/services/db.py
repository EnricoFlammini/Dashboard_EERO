import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
import aiosqlite
from app.config import settings

logger = logging.getLogger(__name__)


class DBService:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(settings.db_file_path)

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    async def init_db(self):
        """Initialize database schema with tables and indexes."""
        logger.info(f"Initializing database at: {self.db_path}")
        async with self.get_connection() as db:
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA synchronous = NORMAL;")
            
            # Clean up obsolete bandwidth metrics tables
            await db.execute("DROP TABLE IF EXISTS wan_metrics;")
            await db.execute("DROP TABLE IF EXISTS device_metrics;")

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

            # Pulizia automatica completa dei dati mock/demo
            await self.purge_all_mock_data()

            await db.commit()
            logger.info("Database schema initialized successfully.")

    async def purge_all_mock_data(self):
        """Elimina completamente tutti i dati mock/demo sia da device_metrics che da wan_metrics e speedtests."""
        demo_macs = [
            '00:11:32:9F:88:44', 'B4:2E:99:A1:01:10', 'F4:F5:DB:33:44:55',
            '28:70:4E:88:99:AA', 'A8:5E:45:12:34:56', '48:E7:DA:99:88:77',
            '18:84:30:11:22:33', 'E0:4F:43:AA:BB:CC', '52:54:00:12:34:56',
            '94:9F:3E:22:33:44', 'A4:C3:F0:11:22:33', 'dev_01', 'dev_02', 'dev_03'
        ]
        demo_hostnames = [
            'Home NAS & Media Server', 'MacBook Pro Lavoro', 'Smart TV OLED 65"',
            'iPhone Personale', 'PS5 Pro Console', 'Shelly Domotica Quadro',
            'Termostato Soggiorno', 'iPad Cucina / Ricette', 'Home Assistant Server',
            'Sonos Speaker Salone', 'Synology-DS920Plus', 'iPhone-15-Pro',
            'Sony-Bravia-OLED-4K', 'PlayStation-5', 'Shelly-Pro-4PM',
            'Sonos-One-Gen2', 'HomeAssistant-NUC', 'iPad-Air-M1'
        ]
        try:
            async with self.get_connection() as db:
                pm = ",".join("?" for _ in demo_macs)
                ph = ",".join("?" for _ in demo_hostnames)
                await db.execute(
                    f"DELETE FROM device_metrics WHERE mac_address IN ({pm}) OR hostname IN ({ph});",
                    (*demo_macs, *demo_hostnames)
                )
                await db.execute("DELETE FROM wan_metrics WHERE public_ip IN ('93.42.180.55', '1.2.3.4', '0.0.0.0') OR download_speed_mbps > 160.0;")
                await db.execute("DELETE FROM speedtests WHERE server_name LIKE '%Fastweb Milan%' OR server_name LIKE '%Demo%' OR server_name LIKE '%synthetics%';")
                await db.commit()
                logger.info("Purged all demo/mock metrics records from SQLite.")
        except Exception as e:
            logger.warning(f"Error purging mock data: {e}")

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
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        async with self.get_connection() as db:
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
        hours = hours or 24
        async with self.get_connection() as db:
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
                since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
                since_iso = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
                query = """
                    SELECT timestamp, status, public_ip, rx_bytes, tx_bytes, 
                           download_speed_mbps, upload_speed_mbps 
                    FROM wan_metrics 
                    WHERE timestamp >= ? OR timestamp >= ?
                    ORDER BY timestamp ASC
                """
                cursor = await db.execute(query, (since, since_iso))
            rows = await cursor.fetchall()
            results = [dict(row) for row in rows]

            return results

    # ----------------- DEVICE METRICS -----------------
    async def save_device_metrics_batch(self, metrics_list: List[Dict[str, Any]]):
        if not metrics_list:
            return
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        async with self.get_connection() as db:
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
        since_iso = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT timestamp, mac_address, hostname, rx_bytes, tx_bytes, download_rate, upload_rate
                FROM device_metrics
                WHERE mac_address = ? AND (timestamp >= ? OR timestamp >= ?)
                ORDER BY timestamp ASC
                """,
                (mac_address, since, since_iso)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_top_bandwidth_hogs(self, hours: int = 24, limit: int = 10) -> List[Dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        since_iso = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            poll_interval = float(await self.get_setting("poll_interval", str(settings.poll_interval)))
        except Exception:
            poll_interval = 30.0

        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT 
                    dm.mac_address,
                    COALESCE(meta.custom_name, dm.hostname, dm.mac_address) as display_name,
                    COALESCE(meta.custom_icon, 'device') as custom_icon,
                    COALESCE(meta.category, 'Altro') as category,
                    MAX(dm.rx_bytes) - MIN(dm.rx_bytes) as delta_rx,
                    MAX(dm.tx_bytes) - MIN(dm.tx_bytes) as delta_tx,
                    MAX(dm.rx_bytes) as max_rx,
                    MAX(dm.tx_bytes) as max_tx,
                    AVG(dm.download_rate) as avg_download_rate,
                    AVG(dm.upload_rate) as avg_upload_rate,
                    SUM(dm.download_rate) as sum_download_rate,
                    SUM(dm.upload_rate) as sum_upload_rate,
                    COUNT(*) as samples_count
                FROM device_metrics dm
                LEFT JOIN device_metadata meta ON dm.mac_address = meta.mac_address
                WHERE dm.timestamp >= ? OR dm.timestamp >= ?
                GROUP BY dm.mac_address
                HAVING (MAX(dm.rx_bytes) - MIN(dm.rx_bytes) + MAX(dm.tx_bytes) - MIN(dm.tx_bytes)) > 0 
                       OR SUM(dm.download_rate) > 0 OR SUM(dm.upload_rate) > 0
                ORDER BY (
                    (MAX(dm.rx_bytes) - MIN(dm.rx_bytes) + MAX(dm.tx_bytes) - MIN(dm.tx_bytes)) + 
                    (SUM(dm.download_rate) + SUM(dm.upload_rate)) * 125000.0 * ?
                ) DESC
                LIMIT ?
                """,
                (since, since_iso, poll_interval, limit)
            )
            rows = await cursor.fetchall()
            results = []
            for r in rows:
                row_dict = dict(r)
                delta_rx = max(0.0, float(row_dict.get("delta_rx") or 0.0))
                delta_tx = max(0.0, float(row_dict.get("delta_tx") or 0.0))
                sum_dl = float(row_dict.get("sum_download_rate") or 0.0)
                sum_ul = float(row_dict.get("sum_upload_rate") or 0.0)

                # Se ci sono contatori hardware di byte delta da eero
                if (delta_rx + delta_tx) > 0:
                    rx_bytes = delta_rx
                    tx_bytes = delta_tx
                else:
                    # Integrazione fisica reale dei campioni di velocità rilevati dal poller:
                    # Byte = sum(Mbps) * 1_000_000 / 8 * poll_interval
                    rx_bytes = (sum_dl * 1_000_000.0 / 8.0) * poll_interval
                    tx_bytes = (sum_ul * 1_000_000.0 / 8.0) * poll_interval

                tot = rx_bytes + tx_bytes
                row_dict["total_rx_bytes"] = rx_bytes
                row_dict["total_tx_bytes"] = tx_bytes
                row_dict["total_bytes"] = tot
                results.append(row_dict)
            return results

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
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        async with self.get_connection() as db:
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
        async with self.get_connection() as db:
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
        async with self.get_connection() as db:
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
                    "avg_ping": round(row["avg_ping"] or 1, 1),
                    "min_ping": round(row["min_ping"] or 1, 1),
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
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM device_metadata")
            rows = await cursor.fetchall()
            return {(row["mac_address"] or "").lower(): dict(row) for row in rows}

    async def get_device_metadata(self, mac_address: str) -> Optional[Dict[str, Any]]:
        mac_clean = (mac_address or "").lower()
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM device_metadata WHERE LOWER(mac_address) = ?", (mac_clean,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def upsert_device_metadata(self, mac_address: str, **kwargs) -> Dict[str, Any]:
        mac_clean = (mac_address or "").lower()
        existing = await self.get_device_metadata(mac_clean)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if existing:
            updated = {**existing, **kwargs, "updated_at": now}
            async with self.get_connection() as db:
                await db.execute(
                    """
                    UPDATE device_metadata
                    SET custom_name = ?, custom_icon = ?, category = ?, 
                        custom_notes = ?, static_ip = ?, is_favorite = ?, 
                        is_low_latency_target = ?, updated_at = ?
                    WHERE LOWER(mac_address) = ?
                    """,
                    (
                        updated.get("custom_name"),
                        updated.get("custom_icon", "device"),
                        updated.get("category", "Altro"),
                        updated.get("custom_notes"),
                        updated.get("static_ip"),
                        1 if bool(updated.get("is_favorite", False)) else 0,
                        1 if bool(updated.get("is_low_latency_target", False)) else 0,
                        now,
                        mac_clean
                    )
                )
                await db.commit()
            return updated
        else:
            new_item = {
                "mac_address": mac_clean,
                "custom_name": kwargs.get("custom_name"),
                "custom_icon": kwargs.get("custom_icon", "device"),
                "category": kwargs.get("category", "Altro"),
                "custom_notes": kwargs.get("custom_notes"),
                "static_ip": kwargs.get("static_ip"),
                "is_favorite": 1 if bool(kwargs.get("is_favorite", False)) else 0,
                "is_low_latency_target": 1 if bool(kwargs.get("is_low_latency_target", False)) else 0,
                "created_at": now,
                "updated_at": now,
            }
            async with self.get_connection() as db:
                await db.execute(
                    """
                    INSERT INTO device_metadata 
                    (mac_address, custom_name, custom_icon, category, custom_notes, static_ip, is_favorite, is_low_latency_target, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        mac_clean,
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
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row["value"] if row else default

    async def set_setting(self, key: str, value: str):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with self.get_connection() as db:
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
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT key, value FROM app_settings")
            rows = await cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}

    # ----------------- ALERTS & NOTIFICATIONS -----------------
    async def save_alert(self, alert_type: str, title: str, message: str) -> int:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with self.get_connection() as db:
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
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT id, timestamp, type, title, message, read FROM alert_history ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def mark_alerts_read(self):
        async with self.get_connection() as db:
            await db.execute("UPDATE alert_history SET read = 1 WHERE read = 0")
            await db.commit()

    # ----------------- RETENTION CLEANUP -----------------
    async def cleanup_old_data(self, retention_days: Optional[int] = None) -> Dict[str, int]:
        days = retention_days or settings.history_retention_days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        deleted_counts = {}
        async with self.get_connection() as db:
            c3 = await db.execute("DELETE FROM speedtests WHERE timestamp < ?", (cutoff,))
            deleted_counts["speedtests"] = c3.rowcount

            c4 = await db.execute("DELETE FROM alert_history WHERE timestamp < ?", (cutoff,))
            deleted_counts["alert_history"] = c4.rowcount

            await db.commit()
            logger.info(f"Data retention cleanup executed (cutoff: {cutoff}): {deleted_counts}")
        return deleted_counts


# Istanza singleton DB
db_service = DBService()
