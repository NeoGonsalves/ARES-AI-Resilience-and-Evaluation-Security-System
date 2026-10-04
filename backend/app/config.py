from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./ares.db"
    environment: str = "development"
    auto_create_schema: bool = True
    allow_dev_identity: bool = True
    prompt_fingerprint_secret: str = "development-only-change-me"
    execution_payload_encryption_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    run_worker: bool = True
    provider_timeout_seconds: float = 60
    cors_origins: str = "http://localhost:5149,https://localhost:7149"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
