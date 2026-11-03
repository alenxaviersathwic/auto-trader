from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.core.filter.base_filter import BaseFilter

SCOPE_VALUES = ("INDEX", "COMMODITY")
SESSION_TYPE_VALUES = ("FULL_AUTO", "SEMI_AUTO", "MANUAL")
SESSION_STATUS_VALUES = ("ACTIVE", "CLOSED", "EXPIRED")


class TradingSessionCreateRequest(BaseModel):
    """Payload for creating a trading session."""

    name: Optional[str] = Field(default=None, max_length=150, description="Blank = auto-generated")
    tradeDate: str = Field(..., min_length=10, max_length=10, description="YYYY-MM-DD, IST trading day")
    userId: int = Field(..., gt=0)
    capital: float = Field(..., gt=0)
    maxLossPercentage: float = Field(default=3.00, gt=0, le=100, description="Session-level loss halt, % of capital")
    scope: str = Field(..., description="INDEX or COMMODITY")
    underlyings: list[str] = Field(default_factory=list, description="Selected index underlyings (scope=INDEX)")
    commodityItems: list[str] = Field(default_factory=list, description="Selected commodities (scope=COMMODITY)")
    sessionType: str = Field(default="MANUAL", description="FULL_AUTO | SEMI_AUTO | MANUAL")
    routeThroughUpstox: bool = Field(default=False, description="False = fully simulated session")

    @model_validator(mode="after")
    def _validate(self) -> "TradingSessionCreateRequest":
        scope = self.scope.upper() if self.scope else self.scope
        if scope not in SCOPE_VALUES:
            raise ValueError(f"scope must be one of {SCOPE_VALUES}")
        if self.sessionType.upper() not in SESSION_TYPE_VALUES:
            raise ValueError(f"sessionType must be one of {SESSION_TYPE_VALUES}")
        if scope == "INDEX" and not self.underlyings:
            raise ValueError("underlyings is required when scope is INDEX")
        if scope == "COMMODITY" and not self.commodityItems:
            raise ValueError("commodityItems is required when scope is COMMODITY")
        return self


class TradingSessionUpdateRequest(BaseModel):
    """Payload for updating a trading session. All fields optional; only provided fields change."""

    name: Optional[str] = Field(default=None, max_length=150)
    capital: Optional[float] = Field(default=None, gt=0)
    maxLossPercentage: Optional[float] = Field(default=None, gt=0, le=100)
    underlyings: Optional[list[str]] = None
    commodityItems: Optional[list[str]] = None
    sessionType: Optional[str] = None
    routeThroughUpstox: Optional[bool] = None
    sessionStatus: Optional[str] = Field(default=None, description="ACTIVE | CLOSED | EXPIRED")

    @model_validator(mode="after")
    def _validate(self) -> "TradingSessionUpdateRequest":
        if self.sessionType is not None and self.sessionType.upper() not in SESSION_TYPE_VALUES:
            raise ValueError(f"sessionType must be one of {SESSION_TYPE_VALUES}")
        if self.sessionStatus is not None and self.sessionStatus.upper() not in SESSION_STATUS_VALUES:
            raise ValueError(f"sessionStatus must be one of {SESSION_STATUS_VALUES}")
        return self


class TradingSessionResponse(BaseModel):
    """Standard trading session response."""

    id: int
    name: str
    tradeDate: str
    userId: int
    capital: float
    maxLossPercentage: float
    scope: str
    underlyings: list[str]
    commodityItems: list[str]
    sessionType: str
    routeThroughUpstox: bool
    sessionStatus: str
    haltReason: Optional[str] = None
    haltedAt: Optional[datetime] = None
    closedAt: Optional[datetime] = None
    status: str
    createdAt: datetime


class TradingSessionSearchFilter(BaseFilter):
    """Search filter for trading sessions."""

    scope: Optional[str] = None
    sessionStatus: Optional[str] = None
    sessionType: Optional[str] = None
    userId: Optional[int] = None
    tradeDate: Optional[str] = None
