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
