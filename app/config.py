from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://crawlforge:crawlforge@localhost:5432/crawlforge"
    redis_url: str = "redis://localhost:6379/0"
    api_key_pepper: SecretStr = Field(default=SecretStr("development-only-change-me"))
    user_agent: str = "CrawlForge/0.1 (+https://github.com/your-org/crawlforge)"
    default_rate_limit_rpm: int = Field(default=60, ge=1, le=100_000)
    default_monthly_quota: int = Field(default=10_000, ge=1)
    scrape_timeout_seconds: int = Field(default=30, ge=1, le=120)
    max_response_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    max_stored_html_bytes: int = Field(default=2 * 1024 * 1024, ge=1024)
    max_stored_markdown_bytes: int = Field(default=1024 * 1024, ge=1024)
    retention_body_days: int = Field(default=7, ge=1)
    retention_record_days: int = Field(default=30, ge=1)
    browser_pool_size: int = Field(default=4, ge=1, le=32)
    http_proxy_urls: list[str] = Field(default_factory=list)
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_base_url: str = "https://api.openai.com/v1"
    otel_exporter_otlp_endpoint: str | None = None
    robots_cache_seconds: int = Field(default=3600, ge=60)
    host_delay_seconds: float = Field(default=0.5, ge=0, le=60)

    @field_validator("http_proxy_urls", mode="before")
    @classmethod
    def parse_proxy_urls(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
