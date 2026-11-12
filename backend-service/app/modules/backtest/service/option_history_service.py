"""
Real option price history on disk, for backtests that price trades from actual premiums (11 Nov 2026 research
review, gap 2) instead of Black-Scholes at a fixed IV.

  fetch_day(day, codes)            1-minute candles of today's / a recent day's LIVE series, +-DAY_STRIKES around
                                   the ATM -> backtest_data/options/<day>/<CODE>/<strike><CE|PE>.csv
  backfill_expired(codes, n)       1-minute candles of the last n EXPIRED series (Upstox Plus "Expired Instruments"
                                   API) -> backtest_data/expired/<CODE>/<expiry>/<strike><CE|PE>.csv

Upstox keeps 1-minute history for about a month, so option_history_job runs fetch_day every trading day after the
close and backfill_expired weekly. Files that already exist are skipped (resumable). CSV columns:
ts, open, high, low, close, volume, oi.
"""
import asyncio
import csv
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.core.logging.logger import logger
from app.modules.opportunities.provider.underlying_config import get_config

API = "https://api.upstox.com"
EXPIRED = f"{API}/v2/expired-instruments"
DATA_DIR = Path(__file__).resolve().parents[4] / "backtest_data"
DAY_STRIKES = 12
EXPIRED_STRIKES = 10
EXPIRED_DAYS_BEFORE = 7
PAUSE_S = 0.2
DEFAULT_CODES = ("NIFTY", "SENSEX", "BANKNIFTY")


async def _token() -> str:
    tok = os.environ.get("UPSTOX_ACCESS_TOKEN")
    if tok:
        return tok
    from app.core.db.session import async_session_factory
    from app.modules.opportunities.provider.upstox_market_data import market_data

    async with async_session_factory() as s:
        return await market_data._token(s)


async def _data(c: httpx.AsyncClient, url: str, **params: Any) -> Any:
    r = await c.get(url, params=params or None)
    await asyncio.sleep(PAUSE_S)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {url.split('?')[0]}: {r.text[:200]}")
    return (r.json() or {}).get("data") or []


def _write(f: Path, candles: list[list[Any]]) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "open", "high", "low", "close", "volume", "oi"])
        w.writerows(sorted(candles))


def _near_atm(strikes: list[float], spot: float | None, n: int) -> set[float]:
    if not spot or not strikes:
        return set(strikes)
    i = strikes.index(min(strikes, key=lambda k: abs(k - spot)))
    return set(strikes[max(0, i - n): i + n + 1])


async def _spot_close(c: httpx.AsyncClient, key: str, day: str) -> float | None:
    k = quote(key, safe="")
    try:
        d = await _data(c, f"{API}/v2/historical-candle/{k}/day/{day}/{day}")
        candles = d.get("candles") if isinstance(d, dict) else None
        if not candles and day == date.today().isoformat():
            d = await _data(c, f"{API}/v2/historical-candle/intraday/{k}/day")
            candles = d.get("candles") if isinstance(d, dict) else None
        return float(candles[0][4]) if candles else None
    except Exception:  # noqa: BLE001
        return None


async def fetch_day(day: str | None = None, codes: tuple[str, ...] | list[str] = DEFAULT_CODES) -> dict[str, int]:
    """Contracts written per underlying for the nearest live expiry on/after `day`."""
    day = day or date.today().isoformat()
    out: dict[str, int] = {}
    headers = {"Authorization": f"Bearer {await _token()}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as c:
        for code in codes:
            cfg = get_config(code)
            try:
                contracts = await _data(c, f"{API}/v2/option/contract", instrument_key=cfg.instrumentKey)
                expiries = sorted({x["expiry"] for x in contracts if x["expiry"] >= day})
                if not expiries:
                    out[code] = 0
                    continue
                legs = [x for x in contracts if x["expiry"] == expiries[0]]
                keep = _near_atm(sorted({float(x["strike_price"]) for x in legs}),
                                 await _spot_close(c, cfg.instrumentKey, day), DAY_STRIKES)
                today = day == date.today().isoformat()
                n = 0
                for x in legs:
                    k = float(x["strike_price"])
                    f = DATA_DIR / "options" / day / code / f"{int(k)}{x['instrument_type']}.csv"
                    if k not in keep or f.exists():
                        continue
                    key = quote(x["instrument_key"], safe="")
                    url = (f"{API}/v2/historical-candle/intraday/{key}/1minute" if today
                           else f"{API}/v2/historical-candle/{key}/1minute/{day}/{day}")
                    d = await _data(c, url)
                    _write(f, d.get("candles", []) if isinstance(d, dict) else [])
                    n += 1
                out[code] = n
            except Exception as e:  # noqa: BLE001 -- one underlying failing must not stop the others
                logger.warning(f"[OPTION_HISTORY] {code} {day}: {type(e).__name__}: {e}")
                out[code] = -1
    return out


async def backfill_expired(codes: tuple[str, ...] | list[str] = DEFAULT_CODES, n_expiries: int = 4,
                           interval: str = "1minute") -> dict[str, int]:
    """Contract files written per underlying over its last n_expiries expired series."""
    out: dict[str, int] = {}
    headers = {"Authorization": f"Bearer {await _token()}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as c:
        for code in codes:
            cfg = get_config(code)
            written = 0
            try:
                expiries = sorted(await _data(c, f"{EXPIRED}/expiries", instrument_key=cfg.instrumentKey))
                expiries = [e for e in expiries if e < date.today().isoformat()][-n_expiries:]
                for exp in expiries:
                    contracts = await _data(c, f"{EXPIRED}/option/contract", instrument_key=cfg.instrumentKey,
                                            expiry_date=exp)
                    keep = _near_atm(sorted({float(x["strike_price"]) for x in contracts}),
                                     await _spot_close(c, cfg.instrumentKey, exp), EXPIRED_STRIKES)
                    to_d = date.fromisoformat(exp)
                    from_d = to_d - timedelta(days=EXPIRED_DAYS_BEFORE + 4)
                    for x in contracts:
                        k = float(x["strike_price"])
                        f = DATA_DIR / "expired" / code / exp / f"{int(k)}{x['instrument_type']}.csv"
                        if k not in keep or f.exists():
                            continue
                        key = quote(x["instrument_key"], safe="")
                        d = await _data(c, f"{EXPIRED}/historical-candle/{key}/{interval}/{to_d}/{from_d}")
                        _write(f, d.get("candles", []) if isinstance(d, dict) else [])
                        written += 1
                out[code] = written
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[OPTION_HISTORY] expired {code}: {type(e).__name__}: {e}")
                out[code] = -1 if not written else written
    return out
