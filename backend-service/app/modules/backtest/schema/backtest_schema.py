from typing import Literal

from pydantic import BaseModel, Field


class RunBacktestRequest(BaseModel):
    dates: list[str] = Field(min_length=1, max_length=30, description="YYYY-MM-DD trading dates to replay")
    codes: list[str] = Field(min_length=1, max_length=6, description="Underlying codes, e.g. NIFTY, BANKNIFTY, SENSEX")


class RangeBacktestRequest(BaseModel):
    fromDate: str = Field(..., min_length=10, max_length=10, description="YYYY-MM-DD, first day (IST)")
    toDate: str = Field(..., min_length=10, max_length=10, description="YYYY-MM-DD, last day (IST), max 95 days later")
    codes: list[str] = Field(min_length=1, max_length=6, description="Index codes, e.g. NIFTY, BANKNIFTY, SENSEX")
    capital: float = Field(default=50000, gt=0, description="Session capital for the portfolio view")
    maxLossPct: float = Field(default=4.0, gt=0, le=100, description="Session daily max loss, % of capital")
    sizing: Literal["MAX_LOTS", "RISK"] = Field(
        default="MAX_LOTS", description="MAX_LOTS = as many lots as current equity buys; RISK = live 1-lot risk sizer")
    managerView: Literal["MY_VIEW", "AI_VIEW"] = Field(
        default="MY_VIEW", description="Session Manager: MY_VIEW (Session Manager 1 · My Experience) or AI_VIEW (Session Manager 2 · Indian Quant Desk)")
    traderFilter: Literal["ALL", "FIB_GOLDEN_TRADER", "FLOW_MOMENTUM_TRADER"] = Field(
        default="ALL", description="Opportunities Trader filter")
    sideFilter: Literal["ALL", "CE", "PE"] = Field(
        default="ALL", description="Option side filter")
    maxParallel: int = Field(default=3, ge=1, le=3, description="Max concurrent open positions")
    guardEnabled: bool = Field(default=True, description="Manager guardrail enabled (0.786+No-FOMO or 15m Time-Stop)")
