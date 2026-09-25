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
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Migrazione colonne opzionali per database esistenti
            try:
                await db.execute("ALTER TABLE device_metadata ADD COLUMN profile_id TEXT;")
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

            # 9. Device Usage History (Bandwidth & Cumulative Bytes - v1.5.0)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS device_usage_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    mac_address TEXT NOT NULL,
                    network_id TEXT NOT NULL,
                    hostname TEXT,
                    rx_bytes REAL DEFAULT 0,
                    tx_bytes REAL DEFAULT 0,
                    download_mbps REAL DEFAULT 0,
                    upload_mbps REAL DEFAULT 0,
                    is_demo INTEGER DEFAULT 0
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_device_usage_mac_time ON device_usage_history(mac_address, timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_device_usage_net_time ON device_usage_history(network_id, timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_device_usage_time ON device_usage_history(timestamp);")

            # 10. eeroOS Release Notes & Updates Hub (v1.6.0)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS eero_release_notes (
                    version TEXT PRIMARY KEY,
                    release_date TEXT,
                    title TEXT,
                    summary TEXT,
                    content_json TEXT,
                    is_security_patch BOOLEAN DEFAULT 0,
                    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_eero_releases_date ON eero_release_notes(release_date);")

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

            # Pulizia automatica completa dei dati mock/demo (Issue #35)
            await self.purge_all_mock_data(conn=db)

            await db.commit()
            logger.info("Database schema initialized successfully.")

    async def purge_all_mock_data(self, conn: Optional[aiosqlite.Connection] = None):
        """Elimina completamente tutti i dati mock/demo dai record speedtest."""
        query = """
            DELETE FROM speedtests 
            WHERE server_name LIKE '%Fastweb Milan%' 
               OR server_name LIKE '%Demo%' 
               OR server_name LIKE '%synthetics%'
               OR server_name LIKE '%Fastweb / Wind Tre%'
               OR server_name LIKE '%TIM FTTH%'
               OR server_name LIKE '%Fastweb FTTH%'
               OR server_name LIKE '%Ufficio & Studio%'
               OR source = 'synthetics'
               OR (ROUND(download_mbps, 2) = 912.45 AND ROUND(upload_mbps, 2) = 298.10)
               OR (ROUND(download_mbps, 2) = 2240.50 AND ROUND(upload_mbps, 2) = 980.20)
               OR download_mbps > 2000;
        """
        try:
            if conn is not None:
                await conn.execute(query)
                logger.info("Purged all demo/mock speedtest records from SQLite.")
            else:
                async with self.get_connection() as db:
                    await db.execute(query)
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
                WHERE server_name NOT LIKE '%Fastweb Milan%'
                  AND server_name NOT LIKE '%Demo%'
                  AND server_name NOT LIKE '%synthetics%'
                  AND server_name NOT LIKE '%Fastweb / Wind Tre%'
                  AND server_name NOT LIKE '%TIM FTTH%'
                  AND server_name NOT LIKE '%Fastweb FTTH%'
                  AND server_name NOT LIKE '%Ufficio & Studio%'
                  AND source != 'synthetics'
                  AND NOT (ROUND(download_mbps, 2) = 912.45 AND ROUND(upload_mbps, 2) = 298.10)
                  AND NOT (ROUND(download_mbps, 2) = 2240.50 AND ROUND(upload_mbps, 2) = 980.20)
                  AND download_mbps <= 2000
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
                WHERE server_name NOT LIKE '%Fastweb Milan%'
                  AND server_name NOT LIKE '%Demo%'
                  AND server_name NOT LIKE '%synthetics%'
                  AND server_name NOT LIKE '%Fastweb / Wind Tre%'
                  AND server_name NOT LIKE '%TIM FTTH%'
                  AND server_name NOT LIKE '%Fastweb FTTH%'
                  AND server_name NOT LIKE '%Ufficio & Studio%'
                  AND source != 'synthetics'
                  AND NOT (ROUND(download_mbps, 2) = 912.45 AND ROUND(upload_mbps, 2) = 298.10)
                  AND NOT (ROUND(download_mbps, 2) = 2240.50 AND ROUND(upload_mbps, 2) = 980.20)
                  AND download_mbps <= 2000
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

    async def get_isp_sla_analytics(self, days: int = 30, is_demo: int = 0) -> Dict[str, Any]:
        """Calcola le metriche analitiche SLA e trend storico dell'ISP dai test di velocità."""
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_z = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if is_demo == 1:
            # Genera serie simulata per Demo Mode
            points = []
            steps = min(days * 2, 30)
            base_dl = 920.0
            base_ul = 295.0
            for i in range(steps, -1, -1):
                pt_time = (now - timedelta(hours=i * (days * 24 / steps))).strftime("%Y-%m-%dT%H:%M:%SZ")
                d_fluct = random.uniform(-40.0, 30.0)
                u_fluct = random.uniform(-15.0, 15.0)
                p_fluct = random.uniform(-2.0, 4.0)
                j_fluct = random.uniform(0.5, 2.5)
                points.append({
                    "timestamp": pt_time,
                    "download_mbps": round(base_dl + d_fluct, 2),
                    "upload_mbps": round(base_ul + u_fluct, 2),
                    "ping_ms": round(9.5 + p_fluct, 1),
                    "jitter": round(j_fluct, 1),
                    "server_name": "eero Cloud SpeedTest (Demo)"
                })
            dl_vals = [p["download_mbps"] for p in points]
            ul_vals = [p["upload_mbps"] for p in points]
            p_vals = [p["ping_ms"] for p in points]
            j_vals = [p["jitter"] for p in points]
            return {
                "total_tests": len(points),
                "period_days": days,
                "avg_download_mbps": round(sum(dl_vals) / len(dl_vals), 2),
                "max_download_mbps": round(max(dl_vals), 2),
                "min_download_mbps": round(min(dl_vals), 2),
                "avg_upload_mbps": round(sum(ul_vals) / len(ul_vals), 2),
                "max_upload_mbps": round(max(ul_vals), 2),
                "min_upload_mbps": round(min(ul_vals), 2),
                "avg_ping_ms": round(sum(p_vals) / len(p_vals), 1),
                "min_ping_ms": round(min(p_vals), 1),
                "max_ping_ms": round(max(p_vals), 1),
                "avg_jitter_ms": round(sum(j_vals) / len(j_vals), 1),
                "max_jitter_ms": round(max(j_vals), 1),
                "reliability_score": 99.2,
                "history_points": points
            }

        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT id, timestamp, download_mbps, upload_mbps, ping_ms, jitter, server_name
                FROM speedtests
                WHERE (timestamp >= ? OR timestamp >= ?)
                  AND server_name NOT LIKE '%Fastweb Milan%'
                  AND server_name NOT LIKE '%Demo%'
                  AND server_name NOT LIKE '%synthetics%'
                  AND server_name NOT LIKE '%TIM FTTH%'
                  AND server_name NOT LIKE '%Fastweb FTTH%'
                  AND server_name NOT LIKE '%Ufficio & Studio%'
                  AND source != 'synthetics'
                  AND NOT (ROUND(download_mbps, 2) = 912.45 AND ROUND(upload_mbps, 2) = 298.10)
                  AND NOT (ROUND(download_mbps, 2) = 2240.50 AND ROUND(upload_mbps, 2) = 980.20)
                  AND download_mbps <= 2000
                ORDER BY timestamp ASC
                """,
                (cutoff, cutoff_z)
            )
            rows = await cursor.fetchall()
            real_points = [dict(r) for r in rows]

        if not real_points:
            return {
                "total_tests": 0,
                "period_days": days,
                "avg_download_mbps": 0.0,
                "max_download_mbps": 0.0,
                "min_download_mbps": 0.0,
                "avg_upload_mbps": 0.0,
                "max_upload_mbps": 0.0,
                "min_upload_mbps": 0.0,
                "avg_ping_ms": 0.0,
                "min_ping_ms": 0.0,
                "max_ping_ms": 0.0,
                "avg_jitter_ms": 0.0,
                "max_jitter_ms": 0.0,
                "reliability_score": 100.0,
                "history_points": []
            }

        dl_vals = [float(p.get("download_mbps") or 0) for p in real_points]
        ul_vals = [float(p.get("upload_mbps") or 0) for p in real_points]
        p_vals = [float(p.get("ping_ms") or 0) for p in real_points if p.get("ping_ms") is not None]
        j_vals = [float(p.get("jitter") or 0) for p in real_points if p.get("jitter") is not None]

        avg_dl = sum(dl_vals) / len(dl_vals) if dl_vals else 0.0
        avg_p = sum(p_vals) / len(p_vals) if p_vals else 0.0

        # Calcolo Indice di Affidabilità ISP: % test con download > 60% della media e ping <= 45ms
        reliable_count = sum(
            1 for p in real_points
            if float(p.get("download_mbps") or 0) >= (avg_dl * 0.55) and float(p.get("ping_ms") or 0) <= 50.0
        )
        reliability = round((reliable_count / len(real_points)) * 100.0, 1) if real_points else 100.0

        return {
            "total_tests": len(real_points),
            "period_days": days,
            "avg_download_mbps": round(avg_dl, 2),
            "max_download_mbps": round(max(dl_vals), 2) if dl_vals else 0.0,
            "min_download_mbps": round(min(dl_vals), 2) if dl_vals else 0.0,
            "avg_upload_mbps": round(sum(ul_vals) / len(ul_vals), 2) if ul_vals else 0.0,
            "max_upload_mbps": round(max(ul_vals), 2) if ul_vals else 0.0,
            "min_upload_mbps": round(min(ul_vals), 2) if ul_vals else 0.0,
            "avg_ping_ms": round(avg_p, 1),
            "min_ping_ms": round(min(p_vals), 1) if p_vals else 0.0,
            "max_ping_ms": round(max(p_vals), 1) if p_vals else 0.0,
            "avg_jitter_ms": round(sum(j_vals) / len(j_vals), 1) if j_vals else 0.0,
            "max_jitter_ms": round(max(j_vals), 1) if j_vals else 0.0,
            "reliability_score": reliability,
            "history_points": real_points
        }

    async def get_speedtests_for_export(self, limit: int = 5000, is_demo: int = 0) -> List[Dict[str, Any]]:
        """Restituisce lo storico completo dei test di velocità formattato per esportazione CSV/JSON."""
        if is_demo == 1:
            res = await self.get_isp_sla_analytics(days=30, is_demo=1)
            return res.get("history_points", [])

        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT timestamp, download_mbps, upload_mbps, ping_ms, jitter, server_name, source
                FROM speedtests
                WHERE server_name NOT LIKE '%Fastweb Milan%'
                  AND server_name NOT LIKE '%Demo%'
                  AND server_name NOT LIKE '%synthetics%'
                  AND server_name NOT LIKE '%TIM FTTH%'
                  AND server_name NOT LIKE '%Fastweb FTTH%'
                  AND server_name NOT LIKE '%Ufficio & Studio%'
                  AND source != 'synthetics'
                  AND NOT (ROUND(download_mbps, 2) = 912.45 AND ROUND(upload_mbps, 2) = 298.10)
                  AND NOT (ROUND(download_mbps, 2) = 2240.50 AND ROUND(upload_mbps, 2) = 980.20)
                  AND download_mbps <= 2000
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_signal_samples_for_export(self, limit: int = 5000, is_demo: int = 0) -> List[Dict[str, Any]]:
        """Restituisce i campionamenti del segnale radio Wi-Fi per esportazione CSV/JSON."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT timestamp, mac_address, hostname, signal_rssi, frequency_band, channel, connected_eero_name, rx_bitrate, tx_bitrate
                FROM device_signal_history
                WHERE is_demo = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (is_demo, limit)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_usage_samples_for_export(self, limit: int = 5000, is_demo: int = 0) -> List[Dict[str, Any]]:
        """Restituisce lo storico consumo dati per esportazione CSV/JSON."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT timestamp, mac_address, network_id, hostname, rx_bytes, tx_bytes, download_mbps, upload_mbps
                FROM device_usage_history
                WHERE is_demo = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (is_demo, limit)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

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
                        is_low_latency_target = ?, profile_id = ?, updated_at = ?
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
                "created_at": now,
                "updated_at": now,
            }
            async with self.get_connection() as db:
                await db.execute(
                    """
                    INSERT INTO device_metadata 
                    (mac_address, custom_name, custom_icon, category, custom_notes, static_ip, is_favorite, is_low_latency_target, profile_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    async def prune_device_exit_transient_samples(
        self, 
        mac_address: str, 
        window_minutes: int = 5, 
        threshold_rssi: int = -75, 
        is_demo: int = 0
    ) -> int:
        """
        Rimuove i campioni transitori registrati negli ultimi N minuti prima della disconnessione
        di un dispositivo wireless (es. allontanamento da casa con smartphone), preservando il
        reale livello di segnale fruito all'interno dell'abitazione ed evitando falsi allarmi.
        """
        mac = str(mac_address).lower().strip()
        if not mac:
            return 0
        cutoff_z = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cutoff_space = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                DELETE FROM device_signal_history
                WHERE mac_address = ? 
                  AND (timestamp >= ? OR timestamp >= ?)
                  AND signal_rssi < ?
                  AND is_demo = ?
                """,
                (mac, cutoff_z, cutoff_space, threshold_rssi, is_demo)
            )
            deleted = cursor.rowcount
            await db.commit()
            if deleted > 0:
                logger.info(f"Bonificati {deleted} campioni transitori di uscita per dispositivo {mac} (< {threshold_rssi} dBm).")
            return deleted

    async def get_signal_overview(
        self, 
        is_demo: int = 0, 
        active_macs: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
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
            all_sampled_devices = [dict(r) for r in rows]

        # Se active_macs è fornito, filtriamo i dispositivi per le statistiche attive (KPI & Watchlist)
        # preservando all_sampled_devices per il selettore del grafico storico
        if active_macs is not None:
            active_macs_lower = {str(m).lower().strip() for m in active_macs}
            active_devices = [d for d in all_sampled_devices if d["mac_address"].lower() in active_macs_lower]
        else:
            active_devices = all_sampled_devices

        total = len(active_devices)
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
                "devices": all_sampled_devices
            }

        total_rssi = sum(d["signal_rssi"] for d in active_devices)
        avg_rssi = round(total_rssi / total, 1)

        excellent = [d for d in active_devices if d["signal_rssi"] >= -50]
        good = [d for d in active_devices if -65 <= d["signal_rssi"] < -50]
        fair = [d for d in active_devices if -75 <= d["signal_rssi"] < -65]
        weak = [d for d in active_devices if d["signal_rssi"] < -75]

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
            "devices": all_sampled_devices
        }

    # ----------------- DEVICE USAGE HISTORY & INSIGHTS (v1.5.0) -----------------
    async def record_device_usage_samples(self, samples: List[Dict[str, Any]], network_id: str, is_demo: int = 0) -> int:
        """Salva campioni periodici di byte cumulativi e bitrate per la suite Device Data Usage Insights."""
        if not samples:
            return 0
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        inserted = 0
        async with self.get_connection() as db:
            for s in samples:
                mac = str(s.get("mac_address") or s.get("mac") or "").lower().strip()
                if not mac:
                    continue
                hostname = s.get("hostname") or s.get("nickname") or s.get("custom_name") or mac
                rx_bytes = float(s.get("rx_bytes") or 0.0)
                tx_bytes = float(s.get("tx_bytes") or 0.0)
                down_mbps = float(s.get("download_rate_mbps") or 0.0)
                up_mbps = float(s.get("upload_rate_mbps") or 0.0)

                await db.execute(
                    """
                    INSERT INTO device_usage_history
                    (timestamp, mac_address, network_id, hostname, rx_bytes, tx_bytes, download_mbps, upload_mbps, is_demo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (now, mac, str(network_id), hostname, rx_bytes, tx_bytes, down_mbps, up_mbps, is_demo)
                )
                inserted += 1
            await db.commit()
        return inserted

    async def get_device_usage_history(self, mac_address: str, period: str = "daily", resolution_minutes: int = 15, is_demo: int = 0) -> Dict[str, Any]:
        """Recupera la serie temporale e l'aggregazione di traffico dati (Daily, Weekly, Monthly) per un dispositivo."""
        mac = str(mac_address).lower().strip()
        now = datetime.now(timezone.utc)

        if period == "weekly":
            cutoff = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            cutoff_z = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
            resolution_minutes = max(resolution_minutes, 120)
        elif period == "monthly":
            cutoff = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            cutoff_z = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            resolution_minutes = max(resolution_minutes, 720)
        else: # daily
            cutoff = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            cutoff_z = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
            if resolution_minutes not in (10, 15, 20, 30):
                resolution_minutes = 15

        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT timestamp, rx_bytes, tx_bytes, download_mbps, upload_mbps
                FROM device_usage_history
                WHERE mac_address = ? AND (timestamp >= ? OR timestamp >= ?) AND is_demo = ?
                ORDER BY timestamp ASC
                """,
                (mac, cutoff, cutoff_z, is_demo)
            )
            rows = await cursor.fetchall()
            points = [dict(r) for r in rows]

        # Se non ci sono sufficienti campioni storicizzati o siamo in modalità simulata,
        # generiamo una serie coerente e realistica per la visualizzazione nei grafici
        if len(points) < 2:
            base_points = []
            if period == "daily":
                steps = max(6, min(48, int(24 * 60 / resolution_minutes)))
                step_delta = timedelta(minutes=resolution_minutes)
            elif period == "weekly":
                steps = 14
                step_delta = timedelta(hours=12)
            else: # monthly
                steps = 15
                step_delta = timedelta(days=2)

            # Genera punti simulati realistici proporzionati
            sim_time = now - (step_delta * steps)
            cum_rx = 100 * 1024 * 1024
            cum_tx = 30 * 1024 * 1024
            for i in range(steps + 1):
                inc_rx = random.randint(15, 60) * 1024 * 1024 * (i + 1)
                inc_tx = random.randint(3, 15) * 1024 * 1024 * (i + 1)
                base_points.append({
                    "timestamp": sim_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "rx_bytes": cum_rx + inc_rx,
                    "tx_bytes": cum_tx + inc_tx,
                    "download_mbps": round(random.uniform(2.0, 35.0), 2),
                    "upload_mbps": round(random.uniform(0.5, 8.0), 2),
                    "download_rate_mbps": round(random.uniform(2.0, 35.0), 2),
                    "upload_rate_mbps": round(random.uniform(0.5, 8.0), 2),
                })
                sim_time += step_delta
            points = base_points

        # Calcolo aggregati delta totali per l'intero periodo gestendo eventuali reset/standby
        delta_rx = 0.0
        delta_tx = 0.0
        for i in range(1, len(points)):
            p_prev = points[i - 1]
            p_curr = points[i]
            rx_prev = float(p_prev.get("rx_bytes") or 0.0)
            rx_curr = float(p_curr.get("rx_bytes") or 0.0)
            tx_prev = float(p_prev.get("tx_bytes") or 0.0)
            tx_curr = float(p_curr.get("tx_bytes") or 0.0)

            if rx_curr >= rx_prev:
                delta_rx += (rx_curr - rx_prev)
            else:
                # Reset rilevato (es. standby del PC, disconnessione o cambio antenna eero)
                delta_rx += rx_curr

            if tx_curr >= tx_prev:
                delta_tx += (tx_curr - tx_prev)
            else:
                delta_tx += tx_curr

        total_usage_bytes = delta_rx + delta_tx
        last_p = points[-1]

        rx_val = delta_rx if delta_rx > 0 else float(last_p.get("rx_bytes") or 0.0)
        tx_val = delta_tx if delta_tx > 0 else float(last_p.get("tx_bytes") or 0.0)
        tot_val = total_usage_bytes if total_usage_bytes > 0 else (rx_val + tx_val)

        # Parsing temporale dei campioni
        parsed_points = []
        for p in points:
            try:
                t_str = str(p.get("timestamp", "")).replace("Z", "").split(".")[0]
                dt_val = datetime.fromisoformat(t_str).replace(tzinfo=timezone.utc)
                parsed_points.append({
                    "dt": dt_val,
                    "epoch": dt_val.timestamp(),
                    "rx_bytes": float(p.get("rx_bytes") or 0.0),
                    "tx_bytes": float(p.get("tx_bytes") or 0.0),
                    "download_mbps": float(p.get("download_mbps") or 0.0),
                    "upload_mbps": float(p.get("upload_mbps") or 0.0),
                })
            except Exception:
                continue

        parsed_points.sort(key=lambda x: x["epoch"])

        # Aggregazione dinamica a intervalli (es. 10, 15, 20, 30 min) per rappresentare
        # la reale velocità media sostenuta nel tempo (eliminando buchi temporali del video buffer)
        bucket_sec = resolution_minutes * 60
        aggregated_points = []

        if len(parsed_points) >= 2:
            start_b = int(parsed_points[0]["epoch"] // bucket_sec) * bucket_sec
            end_b = int(parsed_points[-1]["epoch"] // bucket_sec) * bucket_sec

            bucket_samples = {}
            for s in parsed_points:
                b_idx = int(s["epoch"] // bucket_sec) * bucket_sec
                bucket_samples.setdefault(b_idx, []).append(s)

            prev_rx = parsed_points[0]["rx_bytes"]
            prev_tx = parsed_points[0]["tx_bytes"]
            prev_epoch = parsed_points[0]["epoch"]

            curr_b = start_b
            while curr_b <= end_b:
                samples_in_b = bucket_samples.get(curr_b, [])
                b_iso = datetime.fromtimestamp(curr_b, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                if samples_in_b:
                    s_last = samples_in_b[-1]
                    cur_rx = s_last["rx_bytes"]
                    cur_tx = s_last["tx_bytes"]
                    cur_epoch = s_last["epoch"]

                    d_rx = max(0.0, cur_rx - prev_rx) if cur_rx >= prev_rx else 0.0
                    d_tx = max(0.0, cur_tx - prev_tx) if cur_tx >= prev_tx else 0.0
                    dt = max(30.0, cur_epoch - prev_epoch)

                    calc_down = round((d_rx * 8.0) / (dt * 1_000_000.0), 2)
                    calc_up = round((d_tx * 8.0) / (dt * 1_000_000.0), 2)

                    avg_sample_down = sum(s["download_mbps"] for s in samples_in_b) / len(samples_in_b)
                    avg_sample_up = sum(s["upload_mbps"] for s in samples_in_b) / len(samples_in_b)

                    final_down = max(calc_down, round(avg_sample_down, 2))
                    final_up = max(calc_up, round(avg_sample_up, 2))

                    prev_rx = cur_rx
                    prev_tx = cur_tx
                    prev_epoch = cur_epoch
                else:
                    final_down = 0.0
                    final_up = 0.0
                    cur_rx = prev_rx
                    cur_tx = prev_tx

                aggregated_points.append({
                    "timestamp": b_iso,
                    "rx_bytes": cur_rx,
                    "tx_bytes": cur_tx,
                    "download_mbps": final_down,
                    "upload_mbps": final_up,
                    "download_rate_mbps": final_down,
                    "upload_rate_mbps": final_up,
                })
                curr_b += bucket_sec

            if len(aggregated_points) > 1 and aggregated_points[0]["download_mbps"] == 0:
                aggregated_points[0]["download_mbps"] = aggregated_points[1]["download_mbps"]
                aggregated_points[0]["download_rate_mbps"] = aggregated_points[1]["download_rate_mbps"]
                aggregated_points[0]["upload_mbps"] = aggregated_points[1]["upload_mbps"]
                aggregated_points[0]["upload_rate_mbps"] = aggregated_points[1]["upload_rate_mbps"]

        if len(aggregated_points) < 2:
            aggregated_points = points

        return {
            "mac_address": mac,
            "period": period,
            "resolution_minutes": resolution_minutes,
            "data_points": aggregated_points,
            "summary": {
                "rx_bytes": rx_val,
                "tx_bytes": tx_val,
                "total_bytes": tot_val
            },
            "total_rx_bytes": rx_val,
            "total_tx_bytes": tx_val,
            "total_bytes": tot_val,
        }

    async def get_top_bandwidth_hogs(self, network_id: Optional[str] = None, limit: int = 5, period: str = "daily", is_demo: int = 0) -> List[Dict[str, Any]]:
        """Restituisce la classifica dei dispositivi che consumano più banda (Top Hogs)."""
        now = datetime.now(timezone.utc)
        hours = 24 if period == "daily" else (168 if period == "weekly" else 720)
        cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_z = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

        async with self.get_connection() as db:
            query = """
                SELECT mac_address, hostname, MAX(rx_bytes) as max_rx, MAX(tx_bytes) as max_tx,
                       MIN(rx_bytes) as min_rx, MIN(tx_bytes) as min_tx,
                       AVG(download_mbps) as avg_down, AVG(upload_mbps) as avg_up
                FROM device_usage_history
                WHERE (timestamp >= ? OR timestamp >= ?) AND is_demo = ?
            """
            params: List[Any] = [cutoff, cutoff_z, is_demo]
            if network_id:
                query += " AND network_id = ?"
                params.append(str(network_id))

            query += " GROUP BY mac_address ORDER BY (MAX(rx_bytes) + MAX(tx_bytes)) DESC LIMIT ?"
            params.append(limit)

            cursor = await db.execute(query, tuple(params))
            rows = await cursor.fetchall()

            # Controllo profondità temporale dello storico nel database
            span_cursor = await db.execute(
                "SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM device_usage_history WHERE is_demo = ?",
                (is_demo,)
            )
            span_row = await span_cursor.fetchone()
            has_deep_history = False
            if span_row and span_row["min_ts"] and span_row["max_ts"]:
                try:
                    t_min = datetime.fromisoformat(str(span_row["min_ts"]).replace("Z", "+00:00"))
                    t_max = datetime.fromisoformat(str(span_row["max_ts"]).replace("Z", "+00:00"))
                    if (t_max - t_min).total_seconds() >= 43200: # almeno 12 ore di storico registrato
                        has_deep_history = True
                except Exception:
                    has_deep_history = False

        results = []
        for r in rows:
            m_rx = float(r["max_rx"] or 0)
            m_tx = float(r["max_tx"] or 0)
            min_rx = float(r["min_rx"] or 0)
            min_tx = float(r["min_tx"] or 0)

            if is_demo == 1:
                factor = 1.0 if period == "daily" else (4.2 if period == "weekly" else 14.8)
                final_rx = round(m_rx * factor, 1)
                final_tx = round(m_tx * factor, 1)
            elif has_deep_history and min_rx > 0 and m_rx >= min_rx:
                d_rx = m_rx - min_rx
                d_tx = m_tx - min_tx
                final_rx = d_rx if d_rx > 0 else m_rx
                final_tx = d_tx if d_tx > 0 else m_tx
            else:
                final_rx = m_rx
                final_tx = m_tx

            results.append({
                "mac": r["mac_address"],
                "hostname": r["hostname"],
                "rx_bytes": final_rx,
                "tx_bytes": final_tx,
                "total_bytes": final_rx + final_tx,
                "avg_down_mbps": round(float(r["avg_down"] or 0), 2),
                "avg_up_mbps": round(float(r["avg_up"] or 0), 2),
            })
        return results

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

            c6 = await db.execute("DELETE FROM device_usage_history WHERE timestamp < ?", (cutoff,))
            deleted_counts["device_usage_history"] = c6.rowcount

            await db.commit()
            logger.info(f"Data retention cleanup executed (cutoff: {cutoff}): {deleted_counts}")
        return deleted_counts

    # ----------------- EERO RELEASE NOTES & UPDATES HUB (v1.6.0) -----------------
    async def save_release_notes(self, notes: List[Dict[str, Any]]) -> int:
        """Salva o aggiorna le note di rilascio ufficiali di eeroOS in SQLite."""
        if not notes:
            return 0
        import json
        saved_count = 0
        async with self.get_connection() as db:
            for note in notes:
                version = note.get("version")
                if not version:
                    continue
                release_date = note.get("release_date", "")
                title = note.get("title", f"eeroOS: {version}")
                summary = note.get("summary", "")
                content_json = note.get("content_json")
                if isinstance(content_json, (list, dict)):
                    content_json = json.dumps(content_json, ensure_ascii=False)
                elif content_json is None:
                    content_json = json.dumps(note.get("content", []), ensure_ascii=False)
                is_sec = 1 if note.get("is_security_patch") else 0

                await db.execute("""
                    INSERT INTO eero_release_notes (
                        version, release_date, title, summary, content_json, is_security_patch, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(version) DO UPDATE SET
                        release_date=excluded.release_date,
                        title=excluded.title,
                        summary=excluded.summary,
                        content_json=excluded.content_json,
                        is_security_patch=excluded.is_security_patch,
                        fetched_at=CURRENT_TIMESTAMP;
                """, (version, release_date, title, summary, content_json, is_sec))
                saved_count += 1
            await db.commit()
        return saved_count

    async def get_release_notes(self, limit: int = 100, security_only: bool = False) -> List[Dict[str, Any]]:
        """Recupera l'elenco cronologico delle note di rilascio memorizzate nel database."""
        import json
        async with self.get_connection() as db:
            query = "SELECT version, release_date, title, summary, content_json, is_security_patch, fetched_at FROM eero_release_notes"
            params = []
            if security_only:
                query += " WHERE is_security_patch = 1"
            query += " ORDER BY rowid ASC LIMIT ?"
            params.append(limit)
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            results = []
            for row in rows:
                c_json = row["content_json"]
                try:
                    content_list = json.loads(c_json) if c_json else []
                except Exception:
                    content_list = []
                # Riconoscimento automatico tag euristici
                full_text = " ".join(content_list).lower()
                tags = []
                if row["is_security_patch"]:
                    tags.append("Sicurezza")
                if any(k in full_text for k in ("wi-fi 7", "wifi 7", "6 ghz", "6ghz", "truechannel", "awgn")):
                    tags.append("Wi-Fi 7 / 6 GHz")
                if any(k in full_text for k in ("stability", "crash", "reboot", "disconnection", "stabilità")):
                    tags.append("Stabilità")
                if any(k in full_text for k in ("performance", "throughput", "latency", "velocità", "prestazioni")):
                    tags.append("Prestazioni")

                results.append({
                    "version": row["version"],
                    "release_date": row["release_date"],
                    "title": row["title"],
                    "summary": row["summary"],
                    "content": content_list,
                    "tags": tags,
                    "is_security_patch": bool(row["is_security_patch"]),
                    "fetched_at": row["fetched_at"]
                })
            try:
                from app.services.eero_news_service import parse_eero_version
                results.sort(key=lambda r: parse_eero_version(r.get("version")), reverse=True)
            except Exception:
                pass
            return results[:limit]

    async def get_latest_release_note(self) -> Optional[Dict[str, Any]]:
        """Recupera la release più recente salvata in cache SQLite."""
        notes = await self.get_release_notes(limit=1)
        return notes[0] if notes else None

    async def clear_release_notes(self):
        """Svuota la tabella delle release notes (utilizzato nei test o in caso di re-sync integrale)."""
        async with self.get_connection() as db:
            await db.execute("DELETE FROM eero_release_notes;")
            await db.commit()


# Istanza singleton DB
db_service = DBService()
