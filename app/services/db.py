import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Set
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
                    profile_id TEXT,
                    is_paused INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Migrazione colonne opzionali per database esistenti
            try:
                await db.execute("ALTER TABLE device_metadata ADD COLUMN profile_id TEXT;")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE device_metadata ADD COLUMN is_paused INTEGER DEFAULT 0;")
            except Exception:
                pass

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

            # 7. Known Devices Registry (Persistent MAC registry to prevent duplicate Telegram alerts)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS known_devices (
                    mac_address TEXT PRIMARY KEY,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    hostname TEXT,
                    ip TEXT,
                    notified INTEGER DEFAULT 1
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_known_devices_mac ON known_devices(mac_address);")

            # 8. Device Signal History (RSSI, Band, Channel, Bitrate & Node Storicization - v1.04.00)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS device_signal_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    mac_address TEXT NOT NULL,
                    hostname TEXT,
                    signal_rssi INTEGER NOT NULL,
                    frequency_band TEXT,
                    channel INTEGER,
                    connected_eero_name TEXT,
                    rx_bitrate REAL,
                    tx_bitrate REAL,
                    is_demo INTEGER DEFAULT 0
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_signal_mac_time ON device_signal_history(mac_address, timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_signal_time ON device_signal_history(timestamp);")
            try:
                await db.execute("ALTER TABLE device_signal_history ADD COLUMN is_demo INTEGER DEFAULT 0;")
            except Exception:
                pass

            # Purge all mock demo devices from live signal history table
            await db.execute("""
                DELETE FROM device_signal_history 
                WHERE LOWER(mac_address) IN (
                    'b4:2e:99:a1:01:10', '00:11:32:9f:88:44', 'f4:f5:db:33:44:55',
                    '28:70:4e:88:99:aa', 'a8:5e:45:12:34:56', '48:e7:da:99:88:77',
                    '18:b4:30:11:22:33', 'e0:4f:43:aa:bb:cc', 'dc:a6:32:88:77:66',
                    '7c:49:eb:12:34:78', '3c:22:fb:99:88:77', '70:ee:50:66:77:88',
                    'a4:c3:f0:12:34:56', '94:b9:7e:11:22:33', 'aa:bb:cc:dd:ee:01',
                    'aa:bb:cc:dd:ee:02', '00:1a:2b:3c:4d:5e'
                ) OR hostname IN (
                    'MacBook Pro Lavoro', 'Home NAS & Media Server', 'iPhone Personale',
                    'Smart TV OLED 65"', 'PS5 Pro Console', 'Shelly Domotica Quadro',
                    'Termostato Soggiorno', 'iPad Cucina / Ricette', 'Home Assistant Server',
                    'Sonos Speaker Salone', 'MacBook-Pro-M3', 'Synology-DS920Plus',
                    'iPhone-15-Pro', 'Sony-Bravia-OLED-4K', 'PlayStation-5',
                    'Shelly-Pro-4PM', 'Nest-Thermostat-E', 'Apple-iPad-Air',
                    'RaspberryPi-HomeAssistant', 'Sonos-Era-300-L', 'Telecamera Giardino',
                    'iPhone Test', 'Demo Device'
                ) OR is_demo = 1;
            """)

            # Backfill known_devices from device_metadata
            await db.execute("""
                INSERT OR IGNORE INTO known_devices (mac_address, first_seen, hostname, ip, notified)
                SELECT LOWER(mac_address), created_at, custom_name, static_ip, 1 
                FROM device_metadata 
                WHERE mac_address IS NOT NULL AND mac_address != '';
            """)

            # Inserimento impostazioni predefinite se assenti
            default_settings = [
                ("night_mode_enabled", "false"),
                ("night_mode_start", "23:00"),
                ("night_mode_end", "07:00"),
                ("focus_mode_active", "false"),
                ("focus_mode_paused_macs", "[]"),
                ("telegram_alerts_enabled", "true" if settings.telegram_bot_token else "false"),
                ("webhook_alerts_enabled", "true" if settings.webhook_url else "false"),
                ("daily_digest_enabled", "true"),
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
        """Elimina completamente tutti i dati mock/demo dai record speedtest."""
        try:
            async with self.get_connection() as db:
                await db.execute("DELETE FROM speedtests WHERE server_name LIKE '%Fastweb Milan%' OR server_name LIKE '%Demo%' OR server_name LIKE '%synthetics%';")
                await db.commit()
                logger.info("Purged all demo/mock speedtest records from SQLite.")
        except Exception as e:
            logger.warning(f"Error purging mock data: {e}")

    # ----------------- WAN & DEVICE METRICS (LEGACY/SAFE STUBS) -----------------
    async def get_wan_metrics_history(
        self,
        hours: Optional[int] = 24,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return []

    async def get_device_metrics_history(self, mac_address: str, hours: int = 24) -> List[Dict[str, Any]]:
        return []

    async def get_top_bandwidth_hogs(self, hours: int = 24, limit: int = 10) -> List[Dict[str, Any]]:
        return []

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
                        is_low_latency_target = ?, profile_id = ?, is_paused = ?, updated_at = ?
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
                        updated.get("profile_id"),
                        1 if bool(updated.get("is_paused", False)) else 0,
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
                "profile_id": kwargs.get("profile_id"),
                "is_paused": 1 if bool(kwargs.get("is_paused", False)) else 0,
                "created_at": now,
                "updated_at": now,
            }
            async with self.get_connection() as db:
                await db.execute(
                    """
                    INSERT INTO device_metadata 
                    (mac_address, custom_name, custom_icon, category, custom_notes, static_ip, is_favorite, is_low_latency_target, profile_id, is_paused, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        new_item["profile_id"],
                        new_item["is_paused"],
                        new_item["created_at"],
                        new_item["updated_at"]
                    )
                )
                await db.commit()
            return new_item

    # ----------------- KNOWN DEVICES (PERSISTENT NOTIFICATION TRACKING) -----------------
    async def get_known_device_macs(self) -> Set[str]:
        """Restituisce l'insieme dei MAC address già noti nel database."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT LOWER(mac_address) as mac FROM known_devices")
            rows = await cursor.fetchall()
            return {row["mac"] for row in rows if row["mac"]}

    async def register_known_device(self, mac: str, hostname: str = "", ip: str = "", notified: bool = True):
        """Registra un dispositivo come noto nel database."""
        mac_clean = (mac or "").lower().strip()
        if not mac_clean:
            return
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with self.get_connection() as db:
            await db.execute(
                """
                INSERT INTO known_devices (mac_address, first_seen, hostname, ip, notified)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(mac_address) DO UPDATE SET 
                    hostname = COALESCE(NULLIF(excluded.hostname, ''), known_devices.hostname),
                    ip = COALESCE(NULLIF(excluded.ip, ''), known_devices.ip),
                    notified = CASE WHEN excluded.notified = 1 THEN 1 ELSE known_devices.notified END
                """,
                (mac_clean, now, hostname or "", ip or "", 1 if notified else 0)
            )
            await db.commit()

    async def register_known_devices_batch(self, devices: List[Dict[str, Any]], notified: bool = True):
        """Registra un batch di dispositivi come noti nel database."""
        if not devices:
            return
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        records = []
        for d in devices:
            mac = (d.get("mac") or d.get("mac_address") or "").lower().strip()
            if mac:
                hostname = d.get("custom_name") or d.get("nickname") or d.get("hostname") or ""
                ip = d.get("ip") or ""
                records.append((mac, now, hostname, ip, 1 if notified else 0))
        if records:
            async with self.get_connection() as db:
                await db.executemany(
                    """
                    INSERT OR IGNORE INTO known_devices (mac_address, first_seen, hostname, ip, notified)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    records
                )
                await db.commit()

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

    # ----------------- DEVICE SIGNAL HISTORY (v1.04.00) -----------------
    async def record_device_signal_samples(self, samples: List[Dict[str, Any]], is_demo: int = 0) -> int:
        """Salva in batch i campioni di segnale RSSI dei dispositivi wireless connessi."""
        if not samples:
            return 0
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        inserted = 0
        async with self.get_connection() as db:
            for s in samples:
                mac = str(s.get("mac_address") or s.get("mac") or "").lower().strip()
                rssi = s.get("signal_rssi") or s.get("signal")
                if not mac or rssi is None:
                    continue
                try:
                    rssi_val = int(rssi)
                except Exception:
                    continue
                
                hostname = s.get("hostname") or s.get("custom_name") or s.get("nickname") or mac
                freq_band = s.get("frequency_band") or s.get("wireless_band") or ""
                channel = s.get("channel")
                try:
                    chan_val = int(channel) if channel is not None else None
                except Exception:
                    chan_val = None
                eero_name = s.get("connected_eero_name") or s.get("eero_name") or ""
                rx_rate = s.get("rx_bitrate")
                tx_rate = s.get("tx_bitrate")

                await db.execute(
                    """
                    INSERT INTO device_signal_history 
                    (timestamp, mac_address, hostname, signal_rssi, frequency_band, channel, connected_eero_name, rx_bitrate, tx_bitrate, is_demo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (now, mac, hostname, rssi_val, freq_band, chan_val, eero_name, rx_rate, tx_rate, is_demo)
                )
                inserted += 1
            await db.commit()
        return inserted

    async def get_device_signal_history(self, mac_address: str, range_hours: int = 24, is_demo: int = 0) -> List[Dict[str, Any]]:
        """Recupera la serie temporale del segnale RSSI di uno specifico dispositivo nelle ultime N ore."""
        mac = str(mac_address).lower().strip()
        cutoff_z = (datetime.now(timezone.utc) - timedelta(hours=range_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cutoff_space = (datetime.now(timezone.utc) - timedelta(hours=range_hours)).strftime("%Y-%m-%d %H:%M:%S")
        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT timestamp, mac_address, hostname, signal_rssi, frequency_band, channel, connected_eero_name, rx_bitrate, tx_bitrate
                FROM device_signal_history
                WHERE mac_address = ? AND (timestamp >= ? OR timestamp >= ?) AND is_demo = ?
                ORDER BY timestamp ASC
                """,
                (mac, cutoff_z, cutoff_space, is_demo)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_signal_overview(self, is_demo: int = 0) -> Dict[str, Any]:
        """Calcola le statistiche aggregate di copertura mesh e qualità del segnale RSSI di tutti i dispositivi."""
        async with self.get_connection() as db:
            # Prendi l'ultimo campione per ciascun MAC nelle ultime 6 ore
            cutoff_z = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
            cutoff_space = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
            cursor = await db.execute(
                """
                SELECT h.mac_address, h.hostname, h.signal_rssi, h.frequency_band, h.channel, h.connected_eero_name, h.timestamp
                FROM device_signal_history h
                INNER JOIN (
                    SELECT mac_address, MAX(timestamp) AS max_time
                    FROM device_signal_history
                    WHERE (timestamp >= ? OR timestamp >= ?) AND is_demo = ?
                    GROUP BY mac_address
                ) latest ON h.mac_address = latest.mac_address AND h.timestamp = latest.max_time
                WHERE h.is_demo = ?
                ORDER BY h.hostname COLLATE NOCASE ASC
                """,
                (cutoff_z, cutoff_space, is_demo, is_demo)
            )
            rows = await cursor.fetchall()
            devices = [dict(r) for r in rows]

        total = len(devices)
        if total == 0:
            return {
                "total_wireless_devices": 0,
                "average_rssi": 0,
                "excellent_count": 0,
                "good_count": 0,
                "fair_count": 0,
                "weak_count": 0,
                "excellent_pct": 0,
                "good_pct": 0,
                "fair_pct": 0,
                "weak_pct": 0,
                "weak_devices": [],
                "devices": []
            }

        total_rssi = sum(d["signal_rssi"] for d in devices)
        avg_rssi = round(total_rssi / total, 1)

        excellent = [d for d in devices if d["signal_rssi"] >= -50]
        good = [d for d in devices if -65 <= d["signal_rssi"] < -50]
        fair = [d for d in devices if -75 <= d["signal_rssi"] < -65]
        weak = [d for d in devices if d["signal_rssi"] < -75]

        return {
            "total_wireless_devices": total,
            "average_rssi": avg_rssi,
            "excellent_count": len(excellent),
            "good_count": len(good),
            "fair_count": len(fair),
            "weak_count": len(weak),
            "excellent_pct": round((len(excellent) / total) * 100, 1),
            "good_pct": round((len(good) / total) * 100, 1),
            "fair_pct": round((len(fair) / total) * 100, 1),
            "weak_pct": round((len(weak) / total) * 100, 1),
            "weak_devices": weak,
            "devices": devices
        }

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

            c5 = await db.execute("DELETE FROM device_signal_history WHERE timestamp < ?", (cutoff,))
            deleted_counts["device_signal_history"] = c5.rowcount

            await db.commit()
            logger.info(f"Data retention cleanup executed (cutoff: {cutoff}): {deleted_counts}")
        return deleted_counts


# Istanza singleton DB
db_service = DBService()
