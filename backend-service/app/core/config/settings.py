from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "ordergrid"
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

    # Broker order safety (SEBI retail-algo framework, mandatory from 1 Apr 2026; Upstox API rules)
    # Upstox rejects plain MARKET / SL-M orders from the API since 11 Mar 2026 (UDAPI1158) unless they carry
    # market_protection: -1 = automatic band, 1-25 = % band.
    UPSTOX_MARKET_PROTECTION: int = -1
    # Self-built algos must identify themselves on every order (X-Algo-Name header).
    UPSTOX_ALGO_NAME: str = "auto-trader"
    # Stay well under Upstox's 10 orders/s unregistered-algo limit (and the exchange 10 OPS registration bar).
    ORDER_MAX_PER_SEC: int = 5
    # Entry: marketable LIMIT at the planned price + this many ticks (never chase further). 0.05 = one tick.
    ENTRY_LIMIT_BUFFER_TICKS: int = 2
    # An entry LIMIT not (fully) filled within this many seconds is cancelled: no chasing, no stale resting orders.
    ENTRY_FILL_TIMEOUT_S: float = 3.0

    # Opportunity ranking: CODE = rank by the code baseline (default); LLM = the local model selects.
    # When CODE, the LLM still runs in SHADOW (its pick is logged for A/B) if OPPORTUNITY_LLM_SHADOW is true.
    OPPORTUNITY_RANKER: str = "CODE"
    OPPORTUNITY_LLM_SHADOW: bool = False  # off 13 Nov 2026: no side/paper modes, live flow only

    # Institutional overlays (11 Nov 2026 review). Both are COMPUTED and logged always; they only change trading when
    # enabled, after their validation scripts pass (gamma: scripts/validate_gamma_regime.py t > 2; positioning: A/B).
    GAMMA_ROUTER_ENABLED: bool = False
    POSITIONING_OVERLAY_ENABLED: bool = False
    # 12 Nov 2026 institutional research filters (opportunities/service/institutional_filters.py): comma list of the
    # ones validated on the real-data replay (both halves positive). They only ADD entry requirements.
    # Momentum engine v2 (12 Nov 2026, 6-month replay 4 May-12 Nov, real index data, model option prices):
    #   NIFTY_NOISE_STRICT  real-price month: +80.0k vs +71.9k, both halves better
    #   TREND_5_20 + NO_VWAP_PULLBACK + ENTRY_10_1430: 430 -> 73 trades, -Rs 89.3k -> +Rs 30.2k, PF 0.78 -> 1.38,
    #   max drawdown 1.08L -> 15.6k, total losses 4.1L -> 0.79L; better in BOTH halves (May-Aug16 -108k -> -14.6k,
    #   Aug17-Nov +18.9k -> +44.7k). ENTRY_10_1430 also keeps LATE_DAY_MOMENTUM (net negative over 6 months) out.
    INSTITUTIONAL_FILTERS: str = "NIFTY_NOISE_STRICT,TREND_5_20,NO_VWAP_PULLBACK,ENTRY_10_1430,IB_GATE,PE_EXTRA,DMA50"
    FII_OPEN_CODES: str = "NIFTY"  # FII_OPEN_DRIVE opening trade (fii_open.py); "" = off
    MAX_ONE_LOT_RISK_PCT: float = 4.0  # one lot may risk up to this % of session capital when 0.5% buys < 1 lot (4% = Rs 2,000 at Rs 50k, set 13 Nov 2026)

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
