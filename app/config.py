import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    
    class Settings(BaseSettings):
        """Application settings with environment variable fallbacks."""
        app_name: str = "eero Custom Dashboard & Management Suite"
        app_version: str = "1.03.00"
        debug: bool = False
        
        # Path configuration
        data_dir: str = os.getenv("DATA_DIR", "./data")
        
        # Polling & History
        poll_interval: int = int(os.getenv("POLL_INTERVAL", "10"))
        history_retention_days: int = int(os.getenv("HISTORY_RETENTION_DAYS", "30"))
        speedtest_interval_hours: int = int(os.getenv("SPEEDTEST_INTERVAL_HOURS", "12"))
        
        # Demo Mode
        demo_mode: bool = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")
        
        # Permanent eero Authentication Token (Optional)
        eero_user_token: str = os.getenv("EERO_USER_TOKEN", "")
        eero_network_id: str = os.getenv("EERO_NETWORK_ID", "")

        # Notifications
        telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
        webhook_url: str = os.getenv("WEBHOOK_URL", "")

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore"
        )

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
            self.app_version = "1.03.00"
            self.debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
            self.data_dir = os.getenv("DATA_DIR", "./data")
            self.poll_interval = int(os.getenv("POLL_INTERVAL", "30"))
            self.history_retention_days = int(os.getenv("HISTORY_RETENTION_DAYS", "30"))
            self.speedtest_interval_hours = int(os.getenv("SPEEDTEST_INTERVAL_HOURS", "12"))
            self.demo_mode = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")
            self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
            self.webhook_url = os.getenv("WEBHOOK_URL", "")

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
