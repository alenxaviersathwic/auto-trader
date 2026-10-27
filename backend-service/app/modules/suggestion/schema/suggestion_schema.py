from typing import Any

from pydantic import BaseModel, Field

from app.core.filter.base_filter import BaseFilter


class StartSuggestionRequest(BaseModel):
    confidenceWanted: int = Field(default=70, ge=1, le=100)
    minProfitMargin: float = Field(default=5.0, ge=0, le=500, description="Smallest target, % of premium")
    maxProfitMargin: float = Field(default=10.0, ge=1, le=500, description="Largest target, % of premium")
    maxStopLossPct: float = Field(default=5.0, ge=1, le=50, description="Widest stop, % of premium")
    validMinutes: int = Field(default=15, ge=1, le=120, description="How long a suggestion stays valid")
    maxSuggestions: int = Field(default=10, ge=1, le=30)
    maxPerUnderlying: int = Field(default=2, ge=1, le=5)
    loopGapSeconds: int = Field(default=20, ge=5, le=600)
    indexCount: int = Field(default=5, ge=0, le=6)
    commodityCount: int = Field(default=3, ge=0, le=6)
    underlyings: list[str] | None = Field(default=None, description="Codes to run; null = all selected")
    ignoreMarketHours: bool = Field(default=False, description="Skip the exchange-hours check (testing)")


class StopSuggestionRequest(BaseModel):
    underlyings: list[str] | None = Field(default=None, description="Codes to stop; null = stop all")


class SuggestionFilter(BaseFilter):
    runId: int | None = None
    underlyingCode: str | None = None
    outcome: str | None = None
    latestOnly: bool | None = True


# --- LLM structured answer (picks from the menu only) ---
class AiPick(BaseModel):
    id: str
    rank: int = 0
    confidence: int = 0
    strategy: str = ""
    reasons: list[str] = []
    risks: list[str] = []


class AiAnswer(BaseModel):
    picks: list[AiPick] = []
    noPickReason: str | None = None


class SuggestionResponse(BaseModel):
    id: int
    runId: int
    underlyingCode: str
    underlyingType: str
    contractId: str
    optionType: str
    strike: float
    expiry: str
    entry: float
    stop: float
    target: float
    profitMarginPct: float
    rewardRisk: float
    confidence: int
    rank: int
    strategy: str | None = None
    reasons: list[str] = []
    risks: list[str] = []
    source: str
    validUntil: str
    ageSeconds: int
    outcome: str
    extra: dict[str, Any] = {}
