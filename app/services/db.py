from collections import Counter
import json
import logging
import random
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
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

            # 3. Speedtests (WAN throughput & Bufferbloat)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS speedtests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    download_mbps REAL DEFAULT 0,
                    upload_mbps REAL DEFAULT 0,
                    ping_ms REAL DEFAULT 0,
                    jitter REAL DEFAULT 0,
                    server_name TEXT,
                    source TEXT DEFAULT 'eero_api',
                    ping_under_load REAL DEFAULT 0,
                    bufferbloat_grade TEXT DEFAULT '',
                    bufferbloat_delta_ms REAL DEFAULT 0
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_speedtests_time ON speedtests(timestamp);")
            try:
                await db.execute("ALTER TABLE speedtests ADD COLUMN ping_under_load REAL DEFAULT 0;")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE speedtests ADD COLUMN bufferbloat_grade TEXT DEFAULT '';")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE speedtests ADD COLUMN bufferbloat_delta_ms REAL DEFAULT 0;")
            except Exception:
                pass

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

            # 11. IoT Night Traffic Anomalies (v1.6.0 Module 1)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS iot_traffic_anomalies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    mac_address TEXT NOT NULL,
                    hostname TEXT,
                    device_category TEXT,
                    anomaly_type TEXT NOT NULL,
                    megabytes_transferred REAL NOT NULL,
                    baseline_megabytes REAL DEFAULT 0,
                    severity TEXT NOT NULL,
                    description_it TEXT,
                    description_en TEXT,
                    is_demo INTEGER DEFAULT 0
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_iot_anomalies_time ON iot_traffic_anomalies(timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_iot_anomalies_mac ON iot_traffic_anomalies(mac_address);")

            # 12. Local Users & RBAC Matrix (v1.6.0 Module 1 & 2)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS local_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    display_name TEXT DEFAULT '',
                    role TEXT DEFAULT 'operator',
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    permissions_json TEXT DEFAULT '[]',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_local_users_username ON local_users(username);")

            # Migration check: aggiungi colonne display_name, role, is_active se assenti
            try:
                await db.execute("ALTER TABLE local_users ADD COLUMN display_name TEXT DEFAULT '';")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE local_users ADD COLUMN role TEXT DEFAULT 'operator';")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE local_users ADD COLUMN is_active INTEGER DEFAULT 1;")
            except Exception:
                pass
            await db.execute("UPDATE local_users SET role = 'admin', display_name = 'Admin' WHERE is_admin = 1 AND (role IS NULL OR role = '' OR role = 'operator' OR display_name = 'Amministratore Rete');")

            # 13. Local User Sessions
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES local_users(id) ON DELETE CASCADE
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(token);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);")

            # 14. Device Schedules & Parental Control Automations (v1.6.0 Modulo 1 & 2)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS device_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    target_type TEXT NOT NULL DEFAULT 'devices',
                    target_ids_json TEXT NOT NULL DEFAULT '[]',
                    days_of_week_json TEXT NOT NULL DEFAULT '[]',
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    action TEXT NOT NULL DEFAULT 'pause',
                    enabled INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_device_schedules_enabled ON device_schedules(enabled);")

            # 15. Device Usage Hourly Rollup (v1.6.0 Module 2)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS device_usage_hourly (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hour_timestamp DATETIME NOT NULL,
                    mac_address TEXT NOT NULL,
                    network_id TEXT NOT NULL,
                    hostname TEXT,
                    rx_bytes_delta REAL DEFAULT 0,
                    tx_bytes_delta REAL DEFAULT 0,
                    avg_down_mbps REAL DEFAULT 0,
                    max_down_mbps REAL DEFAULT 0,
                    avg_up_mbps REAL DEFAULT 0,
                    max_up_mbps REAL DEFAULT 0,
                    samples_count INTEGER DEFAULT 0,
                    is_demo INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(mac_address, hour_timestamp, is_demo)
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_usage_hourly_mac_time ON device_usage_hourly(mac_address, hour_timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_usage_hourly_time ON device_usage_hourly(hour_timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_usage_hourly_net_time ON device_usage_hourly(network_id, hour_timestamp);")

            # 16. Device Usage Daily Rollup (v1.6.0 Module 2)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS device_usage_daily (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day_date DATE NOT NULL,
                    mac_address TEXT NOT NULL,
                    network_id TEXT NOT NULL,
                    hostname TEXT,
                    rx_bytes_total REAL DEFAULT 0,
                    tx_bytes_total REAL DEFAULT 0,
                    avg_down_mbps REAL DEFAULT 0,
                    peak_down_mbps REAL DEFAULT 0,
                    avg_up_mbps REAL DEFAULT 0,
                    peak_up_mbps REAL DEFAULT 0,
                    samples_count INTEGER DEFAULT 0,
                    is_demo INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(mac_address, day_date, is_demo)
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_usage_daily_mac_date ON device_usage_daily(mac_address, day_date);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_usage_daily_date ON device_usage_daily(day_date);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_usage_daily_net_date ON device_usage_daily(network_id, day_date);")

            # 17. Device Signal Hourly Rollup (v1.6.0 Module 2)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS device_signal_hourly (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hour_timestamp DATETIME NOT NULL,
                    mac_address TEXT NOT NULL,
                    hostname TEXT,
                    avg_rssi INTEGER NOT NULL,
                    min_rssi INTEGER NOT NULL,
                    max_rssi INTEGER NOT NULL,
                    primary_band TEXT,
                    primary_eero_name TEXT,
                    avg_rx_bitrate REAL DEFAULT 0,
                    avg_tx_bitrate REAL DEFAULT 0,
                    samples_count INTEGER DEFAULT 0,
                    is_demo INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(mac_address, hour_timestamp, is_demo)
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_signal_hourly_mac_time ON device_signal_hourly(mac_address, hour_timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_signal_hourly_time ON device_signal_hourly(hour_timestamp);")

            # 18. System Logs & Diagnostics (v1.6.0 Module 4)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    level TEXT NOT NULL,
                    logger_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_time ON system_logs(timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON system_logs(level);")

            # 19. Discovered Device IPs / Reverse NDP Enrichment (v1.6.0 Modulo 7 - Issue #57)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS device_discovered_ips (
                    mac_address TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    ip_type TEXT DEFAULT 'ULA',
                    source TEXT DEFAULT 'ndp_enrichment',
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (mac_address, ip_address)
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_discovered_ips_mac ON device_discovered_ips(mac_address);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_discovered_ips_time ON device_discovered_ips(last_seen);")

            # Bootstrap utente admin predefinito se la tabella local_users è vuota
            async with db.execute("SELECT COUNT(*) FROM local_users;") as cur_u:
                row_u = await cur_u.fetchone()
                user_cnt = row_u[0] if row_u else 0

            if user_cnt == 0:
                from app.services.auth_service import auth_service, ALL_PERMISSION_KEYS
                admin_u = str(getattr(settings, "admin_user", "admin") or "admin").strip()
                admin_p = str(getattr(settings, "admin_password", "admin") or "admin").strip()
                p_hash, p_salt = auth_service.hash_password(admin_p)
                all_perms_json = json.dumps(ALL_PERMISSION_KEYS)
                await db.execute(
                    """
                    INSERT INTO local_users (username, display_name, role, password_hash, salt, is_admin, is_active, permissions_json, created_at)
                    VALUES (?, 'Admin', 'admin', ?, ?, 1, 1, ?, CURRENT_TIMESTAMP);
                    """,
                    (admin_u, p_hash, p_salt, all_perms_json)
                )
                logger.info(f"Local Auth: Inizializzato utente admin predefinito '{admin_u}'.")
            else:
                from app.services.auth_service import ALL_PERMISSION_KEYS
                # Sincronizza permessi completi per gli amministratori se sono state introdotte nuove chiavi RBAC
                await db.execute(
                    "UPDATE local_users SET permissions_json = ? WHERE is_admin = 1;",
                    (json.dumps(ALL_PERMISSION_KEYS),)
                )

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
                ("log_enabled", "true"),
                ("log_level", "INFO"),
                ("log_retention_days", "7"),
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
        source: str = "eero_api",
        ping_under_load: Optional[float] = None,
        bufferbloat_grade: Optional[str] = None,
        bufferbloat_delta_ms: Optional[float] = None,
    ) -> int:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        p_load = float(ping_under_load) if ping_under_load is not None else float(ping_ms)
        b_delta = float(bufferbloat_delta_ms) if bufferbloat_delta_ms is not None else max(0.0, round(p_load - float(ping_ms), 1))
        if not bufferbloat_grade:
            if b_delta < 5.0:
                b_grade = "A+"
            elif b_delta < 15.0:
                b_grade = "A"
            elif b_delta < 30.0:
                b_grade = "B"
            elif b_delta < 60.0:
                b_grade = "C"
            elif b_delta < 200.0:
                b_grade = "D"
            else:
                b_grade = "F"
        else:
            b_grade = str(bufferbloat_grade)

        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO speedtests 
                (timestamp, download_mbps, upload_mbps, ping_ms, jitter, server_name, source, ping_under_load, bufferbloat_grade, bufferbloat_delta_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now, download_mbps, upload_mbps, ping_ms, jitter, server_name, source, p_load, b_grade, b_delta)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_speedtests(self, limit: int = 50) -> List[Dict[str, Any]]:
        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT id, timestamp, download_mbps, upload_mbps, ping_ms, jitter, server_name, source, ping_under_load, bufferbloat_grade, bufferbloat_delta_ms
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

            # Se i campioni grezzi sono insufficienti o già compattati dal Tier 1, interroga device_usage_hourly
            if len(points) < 2 and period in ("weekly", "monthly") and is_demo == 0:
                h_cur = await db.execute(
                    """
                    SELECT hour_timestamp as timestamp, rx_bytes_delta, tx_bytes_delta, avg_down_mbps, avg_up_mbps
                    FROM device_usage_hourly
                    WHERE mac_address = ? AND is_demo = ? AND hour_timestamp >= ?
                    ORDER BY hour_timestamp ASC
                    """,
                    (mac, is_demo, cutoff)
                )
                h_rows = await h_cur.fetchall()
                if h_rows and len(h_rows) >= 2:
                    cum_rx = 0.0
                    cum_tx = 0.0
                    h_points = []
                    for hr in h_rows:
                        cum_rx += float(hr["rx_bytes_delta"] or 0.0)
                        cum_tx += float(hr["tx_bytes_delta"] or 0.0)
                        h_points.append({
                            "timestamp": hr["timestamp"],
                            "rx_bytes": cum_rx,
                            "tx_bytes": cum_tx,
                            "download_mbps": float(hr["avg_down_mbps"] or 0.0),
                            "upload_mbps": float(hr["avg_up_mbps"] or 0.0),
                            "download_rate_mbps": float(hr["avg_down_mbps"] or 0.0),
                            "upload_rate_mbps": float(hr["avg_up_mbps"] or 0.0),
                        })
                    points = h_points

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

        # Routing veloce: per weekly e monthly, verifica prima la tabella aggregata device_usage_hourly
        if period in ("weekly", "monthly") and is_demo == 0:
            async with self.get_connection() as db:
                h_query = """
                    SELECT mac_address, hostname,
                           SUM(rx_bytes_delta) as sum_rx,
                           SUM(tx_bytes_delta) as sum_tx,
                           AVG(avg_down_mbps) as avg_down,
                           AVG(avg_up_mbps) as avg_up
                    FROM device_usage_hourly
                    WHERE hour_timestamp >= ? AND is_demo = ?
                """
                h_params: List[Any] = [cutoff, is_demo]
                if network_id:
                    h_query += " AND network_id = ?"
                    h_params.append(str(network_id))
                h_query += " GROUP BY mac_address ORDER BY (SUM(rx_bytes_delta) + SUM(tx_bytes_delta)) DESC LIMIT ?"
                h_params.append(limit)

                h_cur = await db.execute(h_query, tuple(h_params))
                h_rows = await h_cur.fetchall()
                if h_rows and len(h_rows) > 0:
                    results = []
                    for hr in h_rows:
                        f_rx = round(float(hr["sum_rx"] or 0), 1)
                        f_tx = round(float(hr["sum_tx"] or 0), 1)
                        results.append({
                            "mac": hr["mac_address"],
                            "hostname": hr["hostname"] or hr["mac_address"],
                            "rx_bytes": f_rx,
                            "tx_bytes": f_tx,
                            "total_bytes": f_rx + f_tx,
                            "avg_down_mbps": round(float(hr["avg_down"] or 0), 2),
                            "avg_up_mbps": round(float(hr["avg_up"] or 0), 2),
                        })
                    return results

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

    # ----------------- MULTI-TIER DATA RETENTION & COMPACTION (v1.6.0 Module 2) -----------------
    async def aggregate_hourly_usage(self, target_hour: datetime) -> int:
        """
        Esegue il rollup orario dei campioni grezzi da device_usage_history
        nella tabella aggregata device_usage_hourly per l'ora specificata.
        """
        h_start = target_hour.replace(minute=0, second=0, microsecond=0)
        h_end = h_start + timedelta(minutes=59, seconds=59)
        start_str = h_start.strftime("%Y-%m-%d %H:%M:%S")
        end_str = h_end.strftime("%Y-%m-%d %H:%M:%S")
        hour_key = h_start.strftime("%Y-%m-%d %H:00:00")

        inserted_or_updated = 0
        async with self.get_connection() as db:
            cur = await db.execute(
                """
                SELECT DISTINCT mac_address, is_demo
                FROM device_usage_history
                WHERE replace(replace(timestamp, 'T', ' '), 'Z', '') BETWEEN ? AND ?
                """,
                (start_str, end_str)
            )
            devices = await cur.fetchall()

            for dev in devices:
                mac = dev["mac_address"]
                is_demo = int(dev["is_demo"] or 0)

                p_cur = await db.execute(
                    """
                    SELECT timestamp, network_id, hostname, rx_bytes, tx_bytes, download_mbps, upload_mbps
                    FROM device_usage_history
                    WHERE mac_address = ? AND is_demo = ? 
                      AND replace(replace(timestamp, 'T', ' '), 'Z', '') BETWEEN ? AND ?
                    ORDER BY replace(replace(timestamp, 'T', ' '), 'Z', '') ASC
                    """,
                    (mac, is_demo, start_str, end_str)
                )
                points = await p_cur.fetchall()
                if not points:
                    continue

                delta_rx = 0.0
                delta_tx = 0.0
                down_speeds = []
                up_speeds = []
                last_net = "0"
                last_host = mac

                # Rileva campione precedente all'ora per calcolare il primo delta
                prev_cur = await db.execute(
                    """
                    SELECT rx_bytes, tx_bytes FROM device_usage_history
                    WHERE mac_address = ? AND is_demo = ? 
                      AND replace(replace(timestamp, 'T', ' '), 'Z', '') < ?
                    ORDER BY replace(replace(timestamp, 'T', ' '), 'Z', '') DESC LIMIT 1
                    """,
                    (mac, is_demo, start_str)
                )
                prev_sample = await prev_cur.fetchone()
                if prev_sample:
                    first_rx = float(points[0]["rx_bytes"] or 0.0)
                    p_rx = float(prev_sample["rx_bytes"] or 0.0)
                    first_tx = float(points[0]["tx_bytes"] or 0.0)
                    p_tx = float(prev_sample["tx_bytes"] or 0.0)
                    delta_rx += (first_rx - p_rx) if first_rx >= p_rx else first_rx
                    delta_tx += (first_tx - p_tx) if first_tx >= p_tx else first_tx

                for i, pt in enumerate(points):
                    last_net = pt["network_id"] or last_net
                    last_host = pt["hostname"] or last_host
                    d_mb = float(pt["download_mbps"] or 0.0)
                    u_mb = float(pt["upload_mbps"] or 0.0)
                    down_speeds.append(d_mb)
                    up_speeds.append(u_mb)

                    if i > 0:
                        rx_prev = float(points[i-1]["rx_bytes"] or 0.0)
                        rx_curr = float(pt["rx_bytes"] or 0.0)
                        tx_prev = float(points[i-1]["tx_bytes"] or 0.0)
                        tx_curr = float(pt["tx_bytes"] or 0.0)
                        delta_rx += (rx_curr - rx_prev) if rx_curr >= rx_prev else rx_curr
                        delta_tx += (tx_curr - tx_prev) if tx_curr >= tx_prev else tx_curr

                avg_down = round(sum(down_speeds) / len(down_speeds), 2) if down_speeds else 0.0
                max_down = round(max(down_speeds), 2) if down_speeds else 0.0
                avg_up = round(sum(up_speeds) / len(up_speeds), 2) if up_speeds else 0.0
                max_up = round(max(up_speeds), 2) if up_speeds else 0.0
                samples_cnt = len(points)

                await db.execute(
                    """
                    INSERT INTO device_usage_hourly
                    (hour_timestamp, mac_address, network_id, hostname, rx_bytes_delta, tx_bytes_delta,
                     avg_down_mbps, max_down_mbps, avg_up_mbps, max_up_mbps, samples_count, is_demo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(mac_address, hour_timestamp, is_demo) DO UPDATE SET
                        network_id = excluded.network_id,
                        hostname = excluded.hostname,
                        rx_bytes_delta = excluded.rx_bytes_delta,
                        tx_bytes_delta = excluded.tx_bytes_delta,
                        avg_down_mbps = excluded.avg_down_mbps,
                        max_down_mbps = excluded.max_down_mbps,
                        avg_up_mbps = excluded.avg_up_mbps,
                        max_up_mbps = excluded.max_up_mbps,
                        samples_count = excluded.samples_count;
                    """,
                    (hour_key, mac, str(last_net), str(last_host), delta_rx, delta_tx,
                     avg_down, max_down, avg_up, max_up, samples_cnt, is_demo)
                )
                inserted_or_updated += 1

            await db.commit()
        return inserted_or_updated

    async def aggregate_daily_usage(self, target_date: Any) -> int:
        """
        Esegue il rollup giornaliero aggregando i record di device_usage_hourly
        nella tabella aggregata device_usage_daily per la data specificata.
        """
        if isinstance(target_date, (datetime, date)):
            day_str = target_date.strftime("%Y-%m-%d")
        else:
            day_str = str(target_date)[:10]

        pattern = f"{day_str}%"
        inserted_or_updated = 0

        async with self.get_connection() as db:
            cur = await db.execute(
                """
                SELECT mac_address, network_id, hostname, is_demo,
                       SUM(rx_bytes_delta) as sum_rx,
                       SUM(tx_bytes_delta) as sum_tx,
                       AVG(avg_down_mbps) as avg_down,
                       MAX(max_down_mbps) as peak_down,
                       AVG(avg_up_mbps) as avg_up,
                       MAX(max_up_mbps) as peak_up,
                       SUM(samples_count) as total_samples
                FROM device_usage_hourly
                WHERE hour_timestamp LIKE ?
                GROUP BY mac_address, is_demo
                """,
                (pattern,)
            )
            rows = await cur.fetchall()

            for r in rows:
                mac = r["mac_address"]
                is_demo = int(r["is_demo"] or 0)
                net_id = r["network_id"] or "0"
                hostname = r["hostname"] or mac
                rx_tot = float(r["sum_rx"] or 0.0)
                tx_tot = float(r["sum_tx"] or 0.0)
                avg_d = round(float(r["avg_down"] or 0.0), 2)
                peak_d = round(float(r["peak_down"] or 0.0), 2)
                avg_u = round(float(r["avg_up"] or 0.0), 2)
                peak_u = round(float(r["peak_up"] or 0.0), 2)
                samples = int(r["total_samples"] or 0)

                await db.execute(
                    """
                    INSERT INTO device_usage_daily
                    (day_date, mac_address, network_id, hostname, rx_bytes_total, tx_bytes_total,
                     avg_down_mbps, peak_down_mbps, avg_up_mbps, peak_up_mbps, samples_count, is_demo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(mac_address, day_date, is_demo) DO UPDATE SET
                        network_id = excluded.network_id,
                        hostname = excluded.hostname,
                        rx_bytes_total = excluded.rx_bytes_total,
                        tx_bytes_total = excluded.tx_bytes_total,
                        avg_down_mbps = excluded.avg_down_mbps,
                        peak_down_mbps = excluded.peak_down_mbps,
                        avg_up_mbps = excluded.avg_up_mbps,
                        peak_up_mbps = excluded.peak_up_mbps,
                        samples_count = excluded.samples_count;
                    """,
                    (day_str, mac, net_id, hostname, rx_tot, tx_tot,
                     avg_d, peak_d, avg_u, peak_u, samples, is_demo)
                )
                inserted_or_updated += 1

            await db.commit()
        return inserted_or_updated

    async def aggregate_hourly_signals(self, target_hour: datetime) -> int:
        """
        Esegue il rollup orario dei campioni di segnale da device_signal_history
        nella tabella aggregata device_signal_hourly per l'ora specificata.
        """
        h_start = target_hour.replace(minute=0, second=0, microsecond=0)
        h_end = h_start + timedelta(minutes=59, seconds=59)
        start_str = h_start.strftime("%Y-%m-%d %H:%M:%S")
        end_str = h_end.strftime("%Y-%m-%d %H:%M:%S")
        hour_key = h_start.strftime("%Y-%m-%d %H:00:00")

        inserted_or_updated = 0
        async with self.get_connection() as db:
            cur = await db.execute(
                """
                SELECT DISTINCT mac_address, is_demo
                FROM device_signal_history
                WHERE replace(replace(timestamp, 'T', ' '), 'Z', '') BETWEEN ? AND ?
                """,
                (start_str, end_str)
            )
            devices = await cur.fetchall()

            for dev in devices:
                mac = dev["mac_address"]
                is_demo = int(dev["is_demo"] or 0)

                p_cur = await db.execute(
                    """
                    SELECT signal_rssi, frequency_band, connected_eero_name, rx_bitrate, tx_bitrate, hostname
                    FROM device_signal_history
                    WHERE mac_address = ? AND is_demo = ?
                      AND replace(replace(timestamp, 'T', ' '), 'Z', '') BETWEEN ? AND ?
                    """,
                    (mac, is_demo, start_str, end_str)
                )
                points = await p_cur.fetchall()
                if not points:
                    continue

                rssis = []
                bands = []
                eeros = []
                rx_rates = []
                tx_rates = []
                hostname = mac

                for pt in points:
                    hostname = pt["hostname"] or hostname
                    r = pt["signal_rssi"]
                    if r is not None and r != 0:
                        rssis.append(int(r))
                    if pt["frequency_band"]:
                        bands.append(str(pt["frequency_band"]))
                    if pt["connected_eero_name"]:
                        eeros.append(str(pt["connected_eero_name"]))
                    if pt["rx_bitrate"] is not None:
                        rx_rates.append(float(pt["rx_bitrate"]))
                    if pt["tx_bitrate"] is not None:
                        tx_rates.append(float(pt["tx_bitrate"]))

                if not rssis:
                    continue

                avg_rssi = int(round(sum(rssis) / len(rssis)))
                min_rssi = min(rssis)
                max_rssi = max(rssis)
                primary_band = Counter(bands).most_common(1)[0][0] if bands else ""
                primary_eero = Counter(eeros).most_common(1)[0][0] if eeros else ""
                avg_rx = round(sum(rx_rates) / len(rx_rates), 2) if rx_rates else 0.0
                avg_tx = round(sum(tx_rates) / len(tx_rates), 2) if tx_rates else 0.0
                samples_cnt = len(points)

                await db.execute(
                    """
                    INSERT INTO device_signal_hourly
                    (hour_timestamp, mac_address, hostname, avg_rssi, min_rssi, max_rssi,
                     primary_band, primary_eero_name, avg_rx_bitrate, avg_tx_bitrate, samples_count, is_demo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(mac_address, hour_timestamp, is_demo) DO UPDATE SET
                        hostname = excluded.hostname,
                        avg_rssi = excluded.avg_rssi,
                        min_rssi = excluded.min_rssi,
                        max_rssi = excluded.max_rssi,
                        primary_band = excluded.primary_band,
                        primary_eero_name = excluded.primary_eero_name,
                        avg_rx_bitrate = excluded.avg_rx_bitrate,
                        avg_tx_bitrate = excluded.avg_tx_bitrate,
                        samples_count = excluded.samples_count;
                    """,
                    (hour_key, mac, hostname, avg_rssi, min_rssi, max_rssi,
                     primary_band, primary_eero, avg_rx, avg_tx, samples_cnt, is_demo)
                )
                inserted_or_updated += 1

            await db.commit()
        return inserted_or_updated

    async def purge_expired_raw_samples(self, raw_retention_hours: Optional[int] = None) -> Dict[str, int]:
        """Elimina i campioni grezzi ad alta frequenza (Tier 1) oltre la soglia configurata (default: 48 ore)."""
        hours = raw_retention_hours or getattr(settings, "retention_raw_hours", 48)
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

        deleted = {}
        async with self.get_connection() as db:
            c1 = await db.execute("DELETE FROM device_usage_history WHERE replace(replace(timestamp, 'T', ' '), 'Z', '') < ?", (cutoff_str,))
            deleted["device_usage_history"] = c1.rowcount
            c2 = await db.execute("DELETE FROM device_signal_history WHERE replace(replace(timestamp, 'T', ' '), 'Z', '') < ?", (cutoff_str,))
            deleted["device_signal_history"] = c2.rowcount
            await db.commit()
            logger.info(f"Tier 1 raw purge executed (cutoff: {cutoff_str}): {deleted}")
        return deleted

    async def purge_expired_hourly_samples(self, hourly_retention_days: Optional[int] = None) -> Dict[str, int]:
        """Elimina i rollup orari (Tier 2) oltre la soglia configurata (default: 30 giorni)."""
        days = hourly_retention_days or getattr(settings, "retention_hourly_days", 30)
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

        deleted = {}
        async with self.get_connection() as db:
            c1 = await db.execute("DELETE FROM device_usage_hourly WHERE hour_timestamp < ?", (cutoff_str,))
            deleted["device_usage_hourly"] = c1.rowcount
            c2 = await db.execute("DELETE FROM device_signal_hourly WHERE hour_timestamp < ?", (cutoff_str,))
            deleted["device_signal_hourly"] = c2.rowcount
            await db.commit()
            logger.info(f"Tier 2 hourly purge executed (cutoff: {cutoff_str}): {deleted}")
        return deleted

    async def purge_expired_daily_samples(self, daily_retention_days: Optional[int] = None) -> Dict[str, int]:
        """Elimina i rollup giornalieri (Tier 3) oltre la soglia configurata (default: 365 giorni)."""
        days = daily_retention_days or getattr(settings, "retention_daily_days", 365)
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_day = cutoff_dt.strftime("%Y-%m-%d")

        deleted = {}
        async with self.get_connection() as db:
            c1 = await db.execute("DELETE FROM device_usage_daily WHERE day_date < ?", (cutoff_day,))
            deleted["device_usage_daily"] = c1.rowcount
            await db.commit()
            logger.info(f"Tier 3 daily purge executed (cutoff: {cutoff_day}): {deleted}")
        return deleted

    async def get_database_stats(self) -> Dict[str, Any]:
        """Restituisce le statistiche su dimensioni fisiche, conteggio righe per tier e salute del database."""
        import os
        db_size_bytes = 0
        wal_size_bytes = 0
        if os.path.exists(self.db_path):
            db_size_bytes = os.path.getsize(self.db_path)
        wal_path = f"{self.db_path}-wal"
        if os.path.exists(wal_path):
            wal_size_bytes = os.path.getsize(wal_path)

        counts = {}
        async with self.get_connection() as db:
            for tbl in ["device_usage_history", "device_usage_hourly", "device_usage_daily",
                        "device_signal_history", "device_signal_hourly", "speedtests",
                        "alert_history", "local_users", "device_schedules", "iot_traffic_anomalies",
                        "system_logs"]:
                try:
                    async with db.execute(f"SELECT COUNT(*) FROM {tbl};") as cur:
                        row = await cur.fetchone()
                        counts[tbl] = row[0] if row else 0
                except Exception:
                    counts[tbl] = 0

            oldest_ts = None
            newest_ts = None
            try:
                async with db.execute("SELECT MIN(timestamp), MAX(timestamp) FROM device_usage_history;") as cur:
                    r = await cur.fetchone()
                    if r and r[0]:
                        oldest_ts = r[0]
                        newest_ts = r[1]
            except Exception:
                pass

        return {
            "db_path": self.db_path,
            "size_bytes": db_size_bytes,
            "size_mb": round(db_size_bytes / (1024 * 1024), 2),
            "wal_size_bytes": wal_size_bytes,
            "wal_size_mb": round(wal_size_bytes / (1024 * 1024), 2),
            "total_size_mb": round((db_size_bytes + wal_size_bytes) / (1024 * 1024), 2),
            "tables": counts,
            "oldest_sample": oldest_ts,
            "newest_sample": newest_ts,
            "retention_policy": {
                "raw_hours": getattr(settings, "retention_raw_hours", 48),
                "hourly_days": getattr(settings, "retention_hourly_days", 30),
                "daily_days": getattr(settings, "retention_daily_days", 365),
                "worker_interval_minutes": getattr(settings, "retention_worker_interval_minutes", 60)
            }
        }

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

    # ----------------- IOT NIGHT ANOMALIES & HISTORIC NODE LOOKUP (v1.6.0) -----------------
    async def save_iot_anomalies(self, anomalies: List[Dict[str, Any]]) -> int:
        """Salva o aggiorna eventi di anomalia sul traffico notturno IoT."""
        if not anomalies:
            return 0
        inserted = 0
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        async with self.get_connection() as db:
            for a in anomalies:
                mac = str(a.get("mac_address") or a.get("mac") or "").lower().strip()
                if not mac:
                    continue
                hostname = a.get("hostname") or mac
                category = a.get("device_category") or "iot"
                anom_type = a.get("anomaly_type") or "excessive_upload"
                mb_transferred = float(a.get("megabytes_transferred") or 0.0)
                baseline_mb = float(a.get("baseline_megabytes") or 0.0)
                severity = a.get("severity") or "warning"
                desc_it = a.get("description_it") or ""
                desc_en = a.get("description_en") or ""
                is_demo = 1 if a.get("is_demo") else 0
                ts = a.get("timestamp") or now

                await db.execute("""
                    INSERT INTO iot_traffic_anomalies (
                        timestamp, mac_address, hostname, device_category, anomaly_type,
                        megabytes_transferred, baseline_megabytes, severity,
                        description_it, description_en, is_demo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ts, mac, hostname, category, anom_type, mb_transferred, baseline_mb, severity, desc_it, desc_en, is_demo))
                inserted += 1
            await db.commit()
        return inserted

    async def get_iot_anomalies(self, limit: int = 50, days: int = 7) -> List[Dict[str, Any]]:
        """Recupera l'elenco delle anomalie di traffico registrate."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_z = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        async with self.get_connection() as db:
            cursor = await db.execute("""
                SELECT id, timestamp, mac_address, hostname, device_category, anomaly_type,
                       megabytes_transferred, baseline_megabytes, severity,
                       description_it, description_en, is_demo
                FROM iot_traffic_anomalies
                WHERE timestamp >= ? OR timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (cutoff, cutoff_z, limit))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def clear_iot_anomalies(self):
        """Svuota la tabella delle anomalie IoT (utilizzato nei test)."""
        async with self.get_connection() as db:
            await db.execute("DELETE FROM iot_traffic_anomalies;")
            await db.commit()

    async def get_device_historic_node_affinity(self, mac_address: str) -> Optional[Dict[str, Any]]:
        """Restituisce il nodo mesh eero a cui il dispositivo ha registrato storicamente il segnale migliore."""
        mac = str(mac_address).lower().strip()
        async with self.get_connection() as db:
            cursor = await db.execute("""
                SELECT connected_eero_name, AVG(signal_rssi) as avg_rssi, COUNT(*) as sample_count
                FROM device_signal_history
                WHERE LOWER(mac_address) = ? AND connected_eero_name IS NOT NULL AND connected_eero_name != ''
                GROUP BY connected_eero_name
                HAVING sample_count >= 2
                ORDER BY avg_rssi DESC
                LIMIT 1
            """, (mac,))
            row = await cursor.fetchone()
            if row:
                return {
                    "best_node": row["connected_eero_name"],
                    "avg_rssi": round(row["avg_rssi"], 1),
                    "samples": row["sample_count"]
                }
        return None

    # =========================================================================
    # LOCAL USERS & SESSIONS (v1.6.0 Module 1 & 2)
    # =========================================================================
    async def get_local_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Recupera un utente locale in base allo username (case-insensitive)."""
        u = str(username).strip().lower()
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM local_users WHERE LOWER(username) = ?;",
                (u,)
            )
            row = await cursor.fetchone()
            if row:
                d = dict(row)
                try:
                    d["permissions"] = json.loads(d.get("permissions_json") or "[]")
                except Exception:
                    d["permissions"] = []
                d["is_admin"] = bool(d.get("is_admin"))
                d["is_active"] = bool(d.get("is_active") if d.get("is_active") is not None else 1)
                d["display_name"] = d.get("display_name") or ""
                d["role"] = d.get("role") or ("admin" if d["is_admin"] else "operator")
                return d
        return None

    async def get_local_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Recupera un utente locale in base al suo ID primario."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM local_users WHERE id = ?;",
                (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                d = dict(row)
                try:
                    d["permissions"] = json.loads(d.get("permissions_json") or "[]")
                except Exception:
                    d["permissions"] = []
                d["is_admin"] = bool(d.get("is_admin"))
                d["is_active"] = bool(d.get("is_active") if d.get("is_active") is not None else 1)
                d["display_name"] = d.get("display_name") or ""
                d["role"] = d.get("role") or ("admin" if d["is_admin"] else "operator")
                return d
        return None

    async def list_local_users(self) -> List[Dict[str, Any]]:
        """Restituisce l'elenco di tutti gli utenti locali registrati (omettendo hash e salt)."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT id, username, display_name, role, is_admin, is_active, permissions_json, created_at, last_login FROM local_users ORDER BY id ASC;"
            )
            rows = await cursor.fetchall()
            users = []
            for r in rows:
                d = dict(r)
                try:
                    d["permissions"] = json.loads(d.get("permissions_json") or "[]")
                except Exception:
                    d["permissions"] = []
                d["is_admin"] = bool(d.get("is_admin"))
                d["is_active"] = bool(d.get("is_active") if d.get("is_active") is not None else 1)
                d["display_name"] = d.get("display_name") or ""
                d["role"] = d.get("role") or ("admin" if d["is_admin"] else "operator")
                d.pop("permissions_json", None)
                users.append(d)
            return users

    async def create_local_user(
        self,
        username: str,
        password_hash: str,
        salt: str,
        display_name: str = "",
        role: str = "operator",
        is_admin: bool = False,
        is_active: bool = True,
        permissions: Optional[List[str]] = None
    ) -> int:
        """Crea un nuovo utente locale e restituisce il suo ID."""
        u = str(username).strip()
        dn = str(display_name or "").strip()
        r = str(role or ("admin" if is_admin else "operator")).strip()
        perms_json = json.dumps(permissions or [])
        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO local_users (username, display_name, role, password_hash, salt, is_admin, is_active, permissions_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (u, dn, r, password_hash, salt, 1 if is_admin else 0, 1 if is_active else 0, perms_json)
            )
            await db.commit()
            return cursor.lastrowid

    async def update_local_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
        role: Optional[str] = None,
        password_hash: Optional[str] = None,
        salt: Optional[str] = None,
        is_admin: Optional[bool] = None,
        is_active: Optional[bool] = None,
        permissions: Optional[List[str]] = None
    ) -> bool:
        """Aggiorna i campi di un utente locale esistente."""
        updates = []
        params = []
        if username is not None:
            updates.append("username = ?")
            params.append(str(username).strip())
        if display_name is not None:
            updates.append("display_name = ?")
            params.append(str(display_name).strip())
        if role is not None:
            updates.append("role = ?")
            params.append(str(role).strip())
        if password_hash is not None and salt is not None:
            updates.append("password_hash = ?")
            params.append(password_hash)
            updates.append("salt = ?")
            params.append(salt)
        if is_admin is not None:
            updates.append("is_admin = ?")
            params.append(1 if is_admin else 0)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        if permissions is not None:
            updates.append("permissions_json = ?")
            params.append(json.dumps(permissions))

        if not updates:
            return False

        params.append(user_id)
        query = f"UPDATE local_users SET {', '.join(updates)} WHERE id = ?;"
        async with self.get_connection() as db:
            cursor = await db.execute(query, tuple(params))
            await db.commit()
            return cursor.rowcount > 0

    async def delete_local_user(self, user_id: int) -> bool:
        """Elimina un utente locale e rimuove a cascata le sue sessioni."""
        async with self.get_connection() as db:
            await db.execute("DELETE FROM user_sessions WHERE user_id = ?;", (user_id,))
            cursor = await db.execute("DELETE FROM local_users WHERE id = ?;", (user_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def count_admin_users(self) -> int:
        """Conta quanti amministratori sono attualmente configurati."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM local_users WHERE is_admin = 1;")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def update_user_last_login(self, user_id: int) -> None:
        """Aggiorna il timestamp di ultimo accesso di un utente."""
        now_str = datetime.now(timezone.utc).isoformat()
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE local_users SET last_login = ? WHERE id = ?;",
                (now_str, user_id)
            )
            await db.commit()

    async def create_user_session(self, user_id: int, duration_days: int = 7) -> str:
        """Genera e memorizza un nuovo token di sessione per l'utente specificato."""
        from app.services.auth_service import auth_service
        token = auth_service.generate_session_token()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=duration_days)
        async with self.get_connection() as db:
            await db.execute(
                """
                INSERT INTO user_sessions (token, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?);
                """,
                (token, user_id, now.isoformat(), expires_at.isoformat())
            )
            await db.commit()
        return token

    async def get_user_by_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verifica un session token e restituisce i dati dell'utente se la sessione è valida e non scaduta."""
        if not token:
            return None
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                SELECT u.id, u.username, u.display_name, u.role, u.is_admin, u.is_active, u.permissions_json, u.created_at, u.last_login, s.expires_at
                FROM user_sessions s
                JOIN local_users u ON s.user_id = u.id
                WHERE s.token = ? AND s.expires_at > ?;
                """,
                (token, now_iso)
            )
            row = await cursor.fetchone()
            if row:
                d = dict(row)
                try:
                    d["permissions"] = json.loads(d.get("permissions_json") or "[]")
                except Exception:
                    d["permissions"] = []
                d["is_admin"] = bool(d.get("is_admin"))
                d["is_active"] = bool(d.get("is_active") if d.get("is_active") is not None else 1)
                d["display_name"] = d.get("display_name") or ""
                d["role"] = d.get("role") or ("admin" if d["is_admin"] else "operator")
                d.pop("permissions_json", None)
                return d
        return None

    async def delete_user_session(self, token: str) -> bool:
        """Elimina la sessione specificata (logout)."""
        if not token:
            return False
        async with self.get_connection() as db:
            cursor = await db.execute("DELETE FROM user_sessions WHERE token = ?;", (token,))
            await db.commit()
            return cursor.rowcount > 0

    async def clear_local_users(self) -> None:
        """Svuota utenti locali e sessioni (utilizzato nei test di integrazione)."""
        async with self.get_connection() as db:
            await db.execute("DELETE FROM user_sessions;")
            await db.execute("DELETE FROM local_users;")
            await db.commit()

    # =========================================================================
    # GESTIONE DEVICE SCHEDULES & PARENTAL CONTROL (v1.6.0 Modulo 1 & 2)
    # =========================================================================
    async def get_device_schedules(self, only_enabled: bool = False) -> List[Dict[str, Any]]:
        """Recupera l'elenco delle pianificazioni configurate."""
        query = "SELECT * FROM device_schedules"
        if only_enabled:
            query += " WHERE enabled = 1"
        query += " ORDER BY id ASC;"
        
        async with self.get_connection() as db:
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["enabled"] = bool(d.get("enabled"))
                try:
                    d["target_ids"] = json.loads(d.get("target_ids_json") or "[]")
                except Exception:
                    d["target_ids"] = []
                try:
                    d["days_of_week"] = json.loads(d.get("days_of_week_json") or "[]")
                except Exception:
                    d["days_of_week"] = []
                results.append(d)
            return results

    async def get_device_schedule_by_id(self, schedule_id: int) -> Optional[Dict[str, Any]]:
        """Recupera una pianificazione per ID."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM device_schedules WHERE id = ?;", (schedule_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["enabled"] = bool(d.get("enabled"))
            try:
                d["target_ids"] = json.loads(d.get("target_ids_json") or "[]")
            except Exception:
                d["target_ids"] = []
            try:
                d["days_of_week"] = json.loads(d.get("days_of_week_json") or "[]")
            except Exception:
                d["days_of_week"] = []
            return d

    async def create_device_schedule(
        self,
        name: str,
        target_type: str,
        target_ids: List[str],
        days_of_week: List[str],
        start_time: str,
        end_time: str,
        action: str = "pause",
        enabled: bool = True
    ) -> int:
        """Crea una nuova regola di pianificazione/parental control."""
        target_ids_json = json.dumps(target_ids)
        days_json = json.dumps(days_of_week)
        async with self.get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO device_schedules (name, target_type, target_ids_json, days_of_week_json, start_time, end_time, action, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (name, target_type, target_ids_json, days_json, start_time, end_time, action, 1 if enabled else 0)
            )
            await db.commit()
            return cursor.lastrowid

    async def update_device_schedule(self, schedule_id: int, **fields) -> bool:
        """Aggiorna i parametri di una pianificazione esistente."""
        allowed_fields = {"name", "target_type", "target_ids", "days_of_week", "start_time", "end_time", "action", "enabled"}
        updates = []
        params = []
        for k, v in fields.items():
            if k not in allowed_fields:
                continue
            if k == "target_ids":
                updates.append("target_ids_json = ?")
                params.append(json.dumps(v))
            elif k == "days_of_week":
                updates.append("days_of_week_json = ?")
                params.append(json.dumps(v))
            elif k == "enabled":
                updates.append("enabled = ?")
                params.append(1 if v else 0)
            else:
                updates.append(f"{k} = ?")
                params.append(v)
        if not updates:
            return False
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(schedule_id)
        
        async with self.get_connection() as db:
            cursor = await db.execute(
                f"UPDATE device_schedules SET {', '.join(updates)} WHERE id = ?;",
                tuple(params)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def delete_device_schedule(self, schedule_id: int) -> bool:
        """Elimina una pianificazione."""
        async with self.get_connection() as db:
            cursor = await db.execute("DELETE FROM device_schedules WHERE id = ?;", (schedule_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def toggle_device_schedule(self, schedule_id: int, enabled: Optional[bool] = None) -> bool:
        """Attiva o disattiva una regola di pianificazione."""
        async with self.get_connection() as db:
            if enabled is None:
                cursor = await db.execute("UPDATE device_schedules SET enabled = 1 - enabled, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (schedule_id,))
            else:
                cursor = await db.execute("UPDATE device_schedules SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (1 if enabled else 0, schedule_id))
            await db.commit()
            return cursor.rowcount > 0

    async def clear_device_schedules(self) -> None:
        """Svuota tutte le pianificazioni (utilizzato nei test)."""
        async with self.get_connection() as db:
            await db.execute("DELETE FROM device_schedules;")
            await db.commit()

    async def run_database_maintenance(self, vacuum: bool = False) -> Dict[str, Any]:
        """Esegue manutenzione e compattazione SQLite (PRAGMA optimize, VACUUM opzionale)."""
        async with self.get_connection() as db:
            async with db.execute("PRAGMA optimize;"):
                pass
            await db.commit()

        if vacuum:
            async with aiosqlite.connect(self.db_path, isolation_level=None) as vac_db:
                try:
                    async with vac_db.execute("PRAGMA wal_checkpoint(TRUNCATE);"):
                        pass
                except Exception as ex_wal:
                    logger.warning(f"WAL checkpoint before vacuum error: {ex_wal}")
                async with vac_db.execute("VACUUM;"):
                    pass
                try:
                    async with vac_db.execute("PRAGMA wal_checkpoint(TRUNCATE);"):
                        pass
                except Exception as ex_wal:
                    logger.warning(f"WAL checkpoint after vacuum error: {ex_wal}")

        logger.info(f"SQLite optimization completed (vacuum={vacuum}).")
        return {
            "status": "success",
            "pragma_optimize": True,
            "vacuum": vacuum,
            "vacuum_performed": vacuum,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ----------------- DISASTER RECOVERY: BACKUP & RESTORE (v1.6.0 Modulo 1) -----------------
    async def export_system_backup(self) -> Dict[str, Any]:
        """
        Esporta un backup atomico completo dello stato di configurazione della dashboard:
        - Metadati dispositivi (nomi, categorie, icone, note, preferiti, IP statici)
        - Impostazioni globali dashboard e automazioni (app_settings)
        - Regole di parental scheduling (device_schedules)
        - Utenti locali e permessi (local_users)
        """
        # 1. Device metadata
        meta_dict = await self.get_all_device_metadata()
        device_metadata_list = list(meta_dict.values())

        # 2. App settings
        app_settings_dict = await self.get_all_settings()

        # 3. Device schedules
        schedules_list = await self.get_device_schedules(only_enabled=False)

        # 4. Local users (elenco completo per ripristino account)
        local_users_list = []
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT id, username, password_hash, salt, is_admin, permissions_json, created_at FROM local_users ORDER BY id ASC;"
            )
            rows = await cursor.fetchall()
            for r in rows:
                user_dict = dict(r)
                if isinstance(user_dict.get("permissions_json"), str):
                    try:
                        user_dict["permissions"] = json.loads(user_dict["permissions_json"])
                    except Exception:
                        user_dict["permissions"] = []
                local_users_list.append(user_dict)

        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "metadata": {
                "backup_version": "1.6.0",
                "schema_version": 1,
                "exported_at": now_iso,
                "app_name": "eero Custom Dashboard",
            },
            "device_metadata": device_metadata_list,
            "app_settings": app_settings_dict,
            "device_schedules": schedules_list,
            "local_users": local_users_list,
        }

    async def import_system_restore(self, backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Esegue il ripristino transazionale atomico dei dati da un payload di backup valido.
        """
        if not isinstance(backup_data, dict):
            raise ValueError("Il payload di backup non è un oggetto JSON valido.")

        meta = backup_data.get("metadata") or {}
        if not meta and "device_metadata" not in backup_data and "app_settings" not in backup_data and "device_schedules" not in backup_data:
            raise ValueError("Struttura del file di backup non riconosciuta o priva di sezioni valide.")

        restored_stats = {
            "device_metadata": 0,
            "app_settings": 0,
            "device_schedules": 0,
            "local_users": 0,
        }

        async with self.get_connection() as db:
            # 1. Ripristino device_metadata
            dev_meta = backup_data.get("device_metadata") or []
            if isinstance(dev_meta, list):
                for dm in dev_meta:
                    mac = str(dm.get("mac_address") or "").lower().strip()
                    if not mac:
                        continue
                    await db.execute(
                        """
                        INSERT INTO device_metadata
                        (mac_address, custom_name, custom_icon, category, custom_notes, static_ip, is_favorite, is_low_latency_target, profile_id, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(mac_address) DO UPDATE SET
                            custom_name = excluded.custom_name,
                            custom_icon = excluded.custom_icon,
                            category = excluded.category,
                            custom_notes = excluded.custom_notes,
                            static_ip = excluded.static_ip,
                            is_favorite = excluded.is_favorite,
                            is_low_latency_target = excluded.is_low_latency_target,
                            profile_id = excluded.profile_id,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (
                            mac,
                            dm.get("custom_name"),
                            dm.get("custom_icon") or "device",
                            dm.get("category") or "Altro",
                            dm.get("custom_notes"),
                            dm.get("static_ip"),
                            1 if dm.get("is_favorite") else 0,
                            1 if dm.get("is_low_latency_target") else 0,
                            dm.get("profile_id"),
                        )
                    )
                    restored_stats["device_metadata"] += 1

            # 2. Ripristino app_settings
            settings_dict = backup_data.get("app_settings") or {}
            if isinstance(settings_dict, dict):
                for k, v in settings_dict.items():
                    if k:
                        await db.execute(
                            """
                            INSERT INTO app_settings (key, value, updated_at)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(key) DO UPDATE SET
                                value = excluded.value,
                                updated_at = CURRENT_TIMESTAMP;
                            """,
                            (str(k), str(v) if v is not None else "")
                        )
                        restored_stats["app_settings"] += 1

            # 3. Ripristino device_schedules
            schedules_list = backup_data.get("device_schedules") or []
            if isinstance(schedules_list, list):
                for sc in schedules_list:
                    name = str(sc.get("name") or "").strip()
                    if not name:
                        continue
                    t_type = sc.get("target_type") or "devices"
                    t_ids = sc.get("target_ids") or []
                    if not isinstance(t_ids, list):
                        t_ids = []
                    d_week = sc.get("days_of_week") or []
                    if not isinstance(d_week, list):
                        d_week = []
                    await db.execute(
                        """
                        INSERT INTO device_schedules
                        (name, target_type, target_ids_json, days_of_week_json, start_time, end_time, action, enabled, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                        """,
                        (
                            name,
                            t_type,
                            json.dumps(t_ids),
                            json.dumps(d_week),
                            sc.get("start_time") or "22:00",
                            sc.get("end_time") or "07:00",
                            sc.get("action") or "pause",
                            1 if sc.get("enabled", True) else 0,
                        )
                    )
                    restored_stats["device_schedules"] += 1

            # 4. Ripristino local_users
            users_list = backup_data.get("local_users") or []
            if isinstance(users_list, list):
                for u in users_list:
                    uname = str(u.get("username") or "").strip()
                    p_hash = u.get("password_hash")
                    p_salt = u.get("salt")
                    if uname and p_hash and p_salt:
                        p_json = json.dumps(u.get("permissions") or [])
                        is_adm = 1 if u.get("is_admin") else 0
                        dn = str(u.get("display_name") or "")
                        role = str(u.get("role") or ("admin" if is_adm else "operator"))
                        is_act = 1 if u.get("is_active", 1) else 0
                        await db.execute(
                            """
                            INSERT INTO local_users (username, display_name, role, password_hash, salt, is_admin, is_active, permissions_json, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(username) DO UPDATE SET
                                display_name = excluded.display_name,
                                role = excluded.role,
                                password_hash = excluded.password_hash,
                                salt = excluded.salt,
                                is_admin = excluded.is_admin,
                                is_active = excluded.is_active,
                                permissions_json = excluded.permissions_json;
                            """,
                            (uname, dn, role, p_hash, p_salt, is_adm, is_act, p_json)
                        )
                        restored_stats["local_users"] += 1

            await db.commit()

        # Log evento allarme
        await self.save_alert(
            alert_type="system_backup_restored",
            title="💾 Ripristino Backup di Sistema Eseguito",
            message=f"Ripristino completato con successo: {restored_stats['device_metadata']} metadati dispositivi, {restored_stats['app_settings']} impostazioni, {restored_stats['device_schedules']} regole orarie e {restored_stats['local_users']} utenti."
        )

        return {
            "status": "success",
            "message": "Ripristino del backup completato con successo.",
            "restored_elements": restored_stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ----------------- SYSTEM LOGS & DIAGNOSTICS (v1.6.0 Module 4) -----------------
    async def get_logging_config(self) -> Dict[str, Any]:
        """Recupera le impostazioni correnti di diagnostica e log di sistema."""
        enabled_val = await self.get_setting("log_enabled", "true")
        level_val = await self.get_setting("log_level", "INFO")
        retention_val = await self.get_setting("log_retention_days", "7")

        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        norm_level = level_val.upper().strip() if level_val and level_val.upper().strip() in valid_levels else "INFO"

        try:
            retention_int = int(retention_val)
        except (ValueError, TypeError):
            retention_int = 7

        return {
            "enabled": str(enabled_val).lower() in ("true", "1", "yes"),
            "level": norm_level,
            "retention_days": retention_int,
        }

    async def set_logging_config(
        self,
        enabled: Optional[bool] = None,
        level: Optional[str] = None,
        retention_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Aggiorna le impostazioni di configurazione log in app_settings."""
        if enabled is not None:
            await self.set_setting("log_enabled", "true" if enabled else "false")
        if level is not None:
            valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            clean_level = level.upper().strip()
            if clean_level in valid_levels:
                await self.set_setting("log_level", clean_level)
        if retention_days is not None:
            await self.set_setting("log_retention_days", str(max(0, int(retention_days))))

        return await self.get_logging_config()

    async def insert_system_log(
        self,
        level: str,
        logger_name: str,
        message: str,
        details_json: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        """Inserisce un singolo evento di log nella tabella system_logs."""
        ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with self.get_connection() as db:
            cur = await db.execute(
                """
                INSERT INTO system_logs (timestamp, level, logger_name, message, details_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ts, level.upper(), logger_name, message, details_json),
            )
            await db.commit()
            return cur.lastrowid

    async def insert_system_logs_batch(self, records: List[Dict[str, Any]]) -> int:
        """Inserimento atomico e massivo di record di log con executemany."""
        if not records:
            return 0
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        params = [
            (
                r.get("timestamp") or now_str,
                str(r.get("level") or "INFO").upper(),
                str(r.get("logger_name") or "root"),
                str(r.get("message") or ""),
                r.get("details_json"),
            )
            for r in records
        ]
        async with self.get_connection() as db:
            cur = await db.executemany(
                """
                INSERT INTO system_logs (timestamp, level, logger_name, message, details_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                params,
            )
            await db.commit()
            return cur.rowcount

    async def get_system_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        level: Optional[str] = None,
        search: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recupera i record di log filtrati con ordinamento decrescente (più recenti prima)."""
        conditions = []
        params = []

        if level and level.strip().upper() != "ALL":
            conditions.append("level = ?")
            params.append(level.strip().upper())

        if search and search.strip():
            conditions.append("(message LIKE ? OR logger_name LIKE ? OR details_json LIKE ?)")
            s_param = f"%{search.strip()}%"
            params.extend([s_param, s_param, s_param])

        if start_time and start_time.strip():
            conditions.append("timestamp >= ?")
            params.append(start_time.strip())

        if end_time and end_time.strip():
            conditions.append("timestamp <= ?")
            params.append(end_time.strip())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT id, timestamp, level, logger_name, message, details_json
            FROM system_logs
            {where_clause}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """
        params.extend([max(1, min(limit, 2000)), max(0, offset)])

        async with self.get_connection() as db:
            cur = await db.execute(query, tuple(params))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_system_logs_count(
        self,
        level: Optional[str] = None,
        search: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> int:
        """Conteggia il numero totale di log che corrispondono ai filtri forniti."""
        conditions = []
        params = []

        if level and level.strip().upper() != "ALL":
            conditions.append("level = ?")
            params.append(level.strip().upper())

        if search and search.strip():
            conditions.append("(message LIKE ? OR logger_name LIKE ? OR details_json LIKE ?)")
            s_param = f"%{search.strip()}%"
            params.extend([s_param, s_param, s_param])

        if start_time and start_time.strip():
            conditions.append("timestamp >= ?")
            params.append(start_time.strip())

        if end_time and end_time.strip():
            conditions.append("timestamp <= ?")
            params.append(end_time.strip())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT COUNT(*) FROM system_logs {where_clause}"

        async with self.get_connection() as db:
            cur = await db.execute(query, tuple(params))
            row = await cur.fetchone()
            return row[0] if row else 0

    async def get_system_logs_stats(self) -> Dict[str, Any]:
        """Restituisce le metriche statistiche aggregate sui log archiviati su SQLite e file."""
        stats = {
            "total_count": 0,
            "level_counts": {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0},
            "oldest_timestamp": None,
            "newest_timestamp": None,
            "file_size_bytes": 0,
            "file_size_mb": 0.0,
        }
        async with self.get_connection() as db:
            cur = await db.execute("SELECT level, COUNT(*) as c FROM system_logs GROUP BY level")
            rows = await cur.fetchall()
            for r in rows:
                lvl = r["level"].upper()
                stats["level_counts"][lvl] = r["c"]
                stats["total_count"] += r["c"]

            cur_t = await db.execute("SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM system_logs")
            row_t = await cur_t.fetchone()
            if row_t:
                stats["oldest_timestamp"] = row_t["min_ts"]
                stats["newest_timestamp"] = row_t["max_ts"]

        try:
            log_p = settings.log_file_path
            if log_p.exists():
                sz = log_p.stat().st_size
                stats["file_size_bytes"] = sz
                stats["file_size_mb"] = round(sz / (1024 * 1024), 2)
        except Exception:
            pass

        return stats

    async def clear_system_logs(self) -> int:
        """Svuota la tabella system_logs e restituisce il numero di righe cancellate."""
        async with self.get_connection() as db:
            cur = await db.execute("SELECT COUNT(*) FROM system_logs")
            row = await cur.fetchone()
            cnt = row[0] if row else 0
            await db.execute("DELETE FROM system_logs")
            await db.commit()
            return cnt

    async def purge_expired_system_logs(self, retention_days: Optional[int] = None) -> int:
        """
        Elimina i log obsoleti in base al periodo di retention (in giorni).
        Se retention_days <= 0 o impostato a 0, la conservazione è illimitata e non viene eliminato nulla.
        """
        if retention_days is None:
            cfg = await self.get_logging_config()
            retention_days = cfg.get("retention_days", 7)

        if retention_days <= 0:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

        async with self.get_connection() as db:
            cur = await db.execute(
                "DELETE FROM system_logs WHERE timestamp < ?",
                (cutoff_str,),
            )
            deleted_count = cur.rowcount if cur.rowcount is not None else 0
            await db.commit()

        if deleted_count > 0:
            logger.info(
                f"Purged {deleted_count} expired system logs older than {cutoff_str} ({retention_days} days retention)."
            )
        return deleted_count

    # =========================================================================
    # DISCOVERED IPS / REVERSE NDP ENRICHMENT (Issue #57)
    # =========================================================================

    async def add_discovered_ips(self, mappings: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Salva o aggiorna associazioni IP-MAC scoperte via NDP o inviate tramite API di ingestion.
        Esegue un UPSERT aggiornando last_seen se la coppia esiste già.
        Restituisce un dizionario con il conteggio di 'added' e 'updated'.
        """
        if not mappings:
            return {"added": 0, "updated": 0, "total": 0}

        added = 0
        updated = 0
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        async with self.get_connection() as db:
            for item in mappings:
                mac = str(item.get("mac") or item.get("mac_address") or "").strip().lower()
                ip = str(item.get("ip") or item.get("ip_address") or "").strip().lower()
                ip_type = str(item.get("ip_type") or item.get("type") or "ULA").strip().upper()
                source = str(item.get("source") or "ndp_enrichment").strip()

                if not mac or not ip or len(mac) < 12:
                    continue

                # Verifica se esiste già
                cur = await db.execute(
                    "SELECT first_seen FROM device_discovered_ips WHERE mac_address = ? AND ip_address = ?",
                    (mac, ip)
                )
                existing = await cur.fetchone()

                if existing:
                    await db.execute(
                        """
                        UPDATE device_discovered_ips 
                        SET last_seen = ?, ip_type = ?, source = ?
                        WHERE mac_address = ? AND ip_address = ?
                        """,
                        (now_str, ip_type, source, mac, ip)
                    )
                    updated += 1
                else:
                    await db.execute(
                        """
                        INSERT INTO device_discovered_ips (mac_address, ip_address, ip_type, source, first_seen, last_seen)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (mac, ip, ip_type, source, now_str, now_str)
                    )
                    added += 1

            await db.commit()

        return {"added": added, "updated": updated, "total": added + updated}

    async def get_discovered_ips_for_mac(self, mac_address: str) -> List[Dict[str, Any]]:
        """Restituisce la lista degli IP scoperti per un dato MAC address."""
        if not mac_address:
            return []
        mac_clean = mac_address.strip().lower()
        async with self.get_connection() as db:
            cur = await db.execute(
                """
                SELECT mac_address, ip_address, ip_type, source, first_seen, last_seen
                FROM device_discovered_ips
                WHERE mac_address = ?
                ORDER BY last_seen DESC
                """,
                (mac_clean,)
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_all_discovered_ips_map(self) -> Dict[str, List[Dict[str, Any]]]:
        """Restituisce una mappa { mac_address: [discovered_ip_dict, ...] } per accesso O(1)."""
        result: Dict[str, List[Dict[str, Any]]] = {}
        async with self.get_connection() as db:
            cur = await db.execute(
                """
                SELECT mac_address, ip_address, ip_type, source, first_seen, last_seen
                FROM device_discovered_ips
                ORDER BY last_seen DESC
                """
            )
            rows = await cur.fetchall()
            for r in rows:
                m = str(r["mac_address"]).strip().lower()
                if m not in result:
                    result[m] = []
                result[m].append(dict(r))
        return result

    async def get_all_discovered_ips_list(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Restituisce l'elenco completo delle associazioni scoperte per endpoint diagnostici/UI."""
        async with self.get_connection() as db:
            cur = await db.execute(
                """
                SELECT mac_address, ip_address, ip_type, source, first_seen, last_seen
                FROM device_discovered_ips
                ORDER BY last_seen DESC
                LIMIT ?
                """,
                (limit,)
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def delete_discovered_ip(self, mac_address: str, ip_address: str) -> bool:
        """Elimina una specifica associazione IP-MAC scoperta."""
        mac_clean = mac_address.strip().lower()
        ip_clean = ip_address.strip().lower()
        async with self.get_connection() as db:
            cur = await db.execute(
                "DELETE FROM device_discovered_ips WHERE mac_address = ? AND ip_address = ?",
                (mac_clean, ip_clean)
            )
            await db.commit()
            return (cur.rowcount or 0) > 0

    async def cleanup_stale_discovered_ips(self, retention_days: int = 30) -> int:
        """Elimina indirizzi scoperti la cui ultima rilevazione supera retention_days."""
        if retention_days <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
        async with self.get_connection() as db:
            cur = await db.execute(
                "DELETE FROM device_discovered_ips WHERE last_seen < ?",
                (cutoff_str,)
            )
            deleted_count = cur.rowcount if cur.rowcount is not None else 0
            await db.commit()
        if deleted_count > 0:
            logger.info(f"NDP Enrichment: Eliminati {deleted_count} IP scoperti obsoleti più vecchi di {cutoff_str}.")
        return deleted_count


# Istanza singleton DB
db_service = DBService()
