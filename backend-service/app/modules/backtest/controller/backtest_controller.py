from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.exception.app_exceptions import NotFoundException
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.modules.backtest.schema.backtest_schema import RangeBacktestRequest, RunBacktestRequest
from app.modules.backtest.service import backtest_service as svc
from app.modules.backtest.service import range_backtest_service as range_svc

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


@backtest_router.post("/backtest/range", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def start_range_backtest(body: RangeBacktestRequest) -> ApiResponse[dict[str, Any]]:
    """Starts a FROM-TO backtest in the background: fetches Upstox candles (+ VIX, NSE participant OI), replays the
    live strategy minute by minute, and reports trades, P&L per index / strategy / day, and what each rule saved or
    cost. Poll GET /backtest/range/{jobId} for progress and the result."""
    job = range_svc.start(body.fromDate, body.toDate, [c.upper() for c in body.codes], body.capital, body.maxLossPct,
                          body.sizing)
    return success(data=job, message=f"Backtest started for {body.fromDate} to {body.toDate}")


@backtest_router.get("/backtest/range/{job_id}", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def range_backtest_status(job_id: str) -> ApiResponse[dict[str, Any]]:
    job = range_svc.status(job_id)
    if not job:
        raise NotFoundException("Backtest job not found (the backend may have restarted)")
    return success(data=job, message=f"Backtest {job['state'].lower()}: {job['stage']}")
