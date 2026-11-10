from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.modules.backtest.schema.backtest_schema import RunBacktestRequest
from app.modules.backtest.service import backtest_service as svc

backtest_router = APIRouter(tags=["Backtest"])
OK = status.HTTP_200_OK


@backtest_router.post("/backtest/run", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def run_backtest(body: RunBacktestRequest, session: AsyncSession = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    """Replays the live engine's rules over real Upstox 1-minute candles for each date x index picked.
    Needs a configured Upstox token; a date/index with no reachable candle data comes back as an
    `error` entry under `runs` rather than a fabricated result."""
    res = await svc.run(body.dates, body.codes, session)
    t = res["totals"]
    message = (f"{t['opportunities']} opportunities across {t['datesRun']} date(s) x {t['indicesRun']} index(es), "
               f"net Rs {t['netPnl']:+,.0f}" + (f" ({t['errors']} could not be fetched)" if t["errors"] else ""))
    return success(data=res, message=message)
