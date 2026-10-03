import os
from pathlib import Path

def _get_default_build_number() -> str:
    env_b = os.getenv("BUILD_NUMBER")
    if env_b and env_b.strip():
        return env_b.strip()
    try:
        f = Path(__file__).resolve().parent.parent / "BUILD_NUMBER"
        if f.exists():
            content = f.read_text(encoding="utf-8").strip()
            if content:
                return content
    except Exception:
        pass
    return "1"


try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    
    class Settings(BaseSettings):
        """Application settings with environment variable fallbacks."""
        app_name: str = "eero Custom Dashboard & Management Suite"
        app_version: str = os.getenv("APP_VERSION", "1.6.0")
        build_number: str = _get_default_build_number()
        debug: bool = False
        
        # Path configuration
        data_dir: str = os.getenv("DATA_DIR", "./data")
        
        # Polling & History
        poll_interval: int = int(os.getenv("POLL_INTERVAL", "10"))
        history_retention_days: int = int(os.getenv("HISTORY_RETENTION_DAYS", "30"))
        speedtest_interval_hours: int = int(os.getenv("SPEEDTEST_INTERVAL_HOURS", "12"))
        
        # Demo Mode
        demo_mode: bool = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")

        # Documentazione interattiva API (/docs, /redoc, /openapi.json): disattivata per default
        api_docs: bool = os.getenv("API_DOCS", "false").lower() in ("true", "1", "yes")
        
        # Permanent eero Authentication Token (Optional)
        eero_user_token: str = os.getenv("EERO_USER_TOKEN", "")
        eero_network_id: str = os.getenv("EERO_NETWORK_ID", "")

        # Notifications & Webhooks
        telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
        webhook_url: str = os.getenv("WEBHOOK_URL", "")
        dashboard_lang: str = os.getenv("DASHBOARD_LANG", "en")

        # CORS: origini esterne consentite, separate da virgola (vuoto = solo stessa origine)
        cors_origins: str = os.getenv("CORS_ORIGINS", "")

        # Auto-Update & Docker Integration
        docker_socket_path: str = os.getenv("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
        watchtower_url: str = os.getenv("WATCHTOWER_URL", "")
        update_check_interval_hours: int = int(os.getenv("UPDATE_CHECK_INTERVAL_HOURS", "6"))

        # Local Authentication & Admin Bootstrap (v1.6.0 Module 1)
        admin_user: str = os.getenv("ADMIN_USER", "admin")
        admin_password: str = os.getenv("ADMIN_PASSWORD", "admin")
        require_local_auth: bool = os.getenv("REQUIRE_LOCAL_AUTH", "false").lower() in ("true", "1", "yes")

        # Data Retention & Multi-Tier Compaction (v1.6.0 Module 2)
        retention_raw_hours: int = int(os.getenv("RETENTION_RAW_HOURS", "48"))
        retention_hourly_days: int = int(os.getenv("RETENTION_HOURLY_DAYS", "30"))
        retention_daily_days: int = int(os.getenv("RETENTION_DAILY_DAYS", "365"))
        retention_worker_interval_minutes: int = int(os.getenv("RETENTION_WORKER_INTERVAL_MINUTES", "60"))

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore"
        )

        @property
        def full_version(self) -> str:
            """Restituisce la versione con numero di build, es. '1.5.0 build 1'."""
            b = str(self.build_number).strip()
            if b:
                return f"{self.app_version} build {b}"
            return self.app_version

        @property
        def data_path(self) -> Path:
            p = Path(self.data_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p

        @property
        def session_file_path(self) -> Path:
            return self.data_path / "session.json"

        @property
        def db_file_path(self) -> Path:
            return self.data_path / "metrics.db"

except ImportError:
    # Standalone lightweight fallback if running outside Docker without pydantic-settings
    class Settings:
        def __init__(self):
            self.app_name = "eero Custom Dashboard & Management Suite"
            self.app_version = os.getenv("APP_VERSION", "1.6.0")
            self.build_number = _get_default_build_number()
            self.debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
            self.data_dir = os.getenv("DATA_DIR", "./data")
            self.poll_interval = int(os.getenv("POLL_INTERVAL", "30"))
            self.history_retention_days = int(os.getenv("HISTORY_RETENTION_DAYS", "30"))
            self.speedtest_interval_hours = int(os.getenv("SPEEDTEST_INTERVAL_HOURS", "12"))
            self.demo_mode = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")
            self.api_docs = os.getenv("API_DOCS", "false").lower() in ("true", "1", "yes")
            self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
            self.webhook_url = os.getenv("WEBHOOK_URL", "")
            self.dashboard_lang = os.getenv("DASHBOARD_LANG", "en")
            self.docker_socket_path = os.getenv("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
            self.watchtower_url = os.getenv("WATCHTOWER_URL", "")
            self.update_check_interval_hours = int(os.getenv("UPDATE_CHECK_INTERVAL_HOURS", "6"))
            self.cors_origins = os.getenv("CORS_ORIGINS", "")
            self.admin_user = os.getenv("ADMIN_USER", "admin")
            self.admin_password = os.getenv("ADMIN_PASSWORD", "admin")
            self.require_local_auth = os.getenv("REQUIRE_LOCAL_AUTH", "false").lower() in ("true", "1", "yes")
            self.retention_raw_hours = int(os.getenv("RETENTION_RAW_HOURS", "48"))
            self.retention_hourly_days = int(os.getenv("RETENTION_HOURLY_DAYS", "30"))
            self.retention_daily_days = int(os.getenv("RETENTION_DAILY_DAYS", "365"))
            self.retention_worker_interval_minutes = int(os.getenv("RETENTION_WORKER_INTERVAL_MINUTES", "60"))

        @property
        def full_version(self) -> str:
            """Restituisce la versione con numero di build, es. '1.5.0 build 1'."""
            b = str(self.build_number).strip()
            if b:
                return f"{self.app_version} build {b}"
            return self.app_version

        @property
        def data_path(self) -> Path:
            p = Path(self.data_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p

        @property
        def session_file_path(self) -> Path:
            return self.data_path / "session.json"

        @property
        def db_file_path(self) -> Path:
            return self.data_path / "metrics.db"


settings = Settings()
