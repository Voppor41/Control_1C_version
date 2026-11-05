from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Control_1C_version"
    environment: Literal["dev", "development", "prod", "production"] = "dev"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/control_1c_version"
    database_pool_size: int = 20
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    seed_demo: bool | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.environment in {"prod", "production"}

    @property
    def should_seed_demo(self) -> bool:
        if self.seed_demo is not None:
            return self.seed_demo
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
