"""
Application settings — all env-driven, never hardcoded secrets.
Copy .env.example → .env and fill in values before running.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = "development"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # Storage
    UPLOAD_DIR: str = "./data/uploads"
    STORE_DIR: str = "./data/store"
    MAX_UPLOAD_MB: int = 50

    # Auth
    ADMIN_TOKEN: str = "change_me_before_deploy"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/store/platform.db"

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def store_path(self) -> Path:
        p = Path(self.STORE_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
