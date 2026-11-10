from pydantic import BaseModel, Field


class RunBacktestRequest(BaseModel):
    dates: list[str] = Field(min_length=1, max_length=30, description="YYYY-MM-DD trading dates to replay")
    codes: list[str] = Field(min_length=1, max_length=6, description="Underlying codes, e.g. NIFTY, BANKNIFTY, SENSEX")
