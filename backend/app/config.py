import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"
METADATA_DIR = ARTIFACTS_DIR / "metadata"

for directory in [
    DATA_DIR,
    DATA_DIR / "raw",
    DATA_DIR / "processed",
    DATA_DIR / "generated",
    DATA_DIR / "reports",
    ARTIFACTS_DIR,
    MODELS_DIR,
    METADATA_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    app_name: str = "FlyGuard AI"
    app_version: str = "1.0.0"
    app_env: str = os.getenv("APP_ENV", "development")
    debug: bool = False

    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{DATA_DIR / 'flyguard.db'}"
    )

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,*"

    default_synthetic_accounts: int = 20000
    default_synthetic_transactions: int = 200000
    default_random_seed: int = 42

    # Configurable Risk Thresholds on 0-100 Normalized Risk Score
    risk_threshold_moderate: float = 35.0
    risk_threshold_high: float = 65.0
    risk_threshold_critical: float = 85.0

    # Production safety guard for database reset
    allow_db_reset: bool = True

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

