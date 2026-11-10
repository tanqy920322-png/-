from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://fitout:fitout@127.0.0.1:5432/fitout"
    redis_url: str = "redis://127.0.0.1:6379/0"
    api_secret: str = "dev-only-change-me"
    storage_dir: str = "./var/storage"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    admin_username: str = "admin"
    admin_password: str = "demo1234"
    test_otp: str = "123456"
    auto_seed: bool = True
    access_token_hours: int = 24 * 14

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
