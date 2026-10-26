from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "auto-trader"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # PostgreSQL async connection URL (pgvector supported)
    DATABASE_URL: str = "postgresql+asyncpg://autotrader:autotrader_secret@localhost:5432/autotrader"

    # Master encryption key (32 bytes or 32-char string for AES-GCM)
    MASTER_ENCRYPTION_KEY: str = "autotrader_master_secret_key_32b!"

    # APScheduler timezone
    SCHEDULER_TIMEZONE: str = "Asia/Kolkata"

    # CORS origins
    CORS_ORIGINS: List[str] = ["*"]

    # Research Engine, LLM & Embeddings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIMENSION: int = 768
    SEARXNG_BASE_URL: str = "http://localhost:8080"
    MCP_RESEARCH_TOKEN: str = "mcp_research_secret_token_123"
    MCP_CONFIRM_SECRET: str = "mcp_confirm_secret_key_32b_hex!"

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
