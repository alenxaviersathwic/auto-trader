"""
Upstox public instrument files -> the contract facts the opportunity engine needs.

Why this exists:
  * Upstox GET /v2/option/chain has NO data for the MCX segment ("Option chain is not available for MCX
    segment" -- Upstox staff, community.upstox.com/t/silver-option-chain/11876). Every commodity card came
    back with zero strikes. The MCX chain is therefore built from this catalogue + market quotes.
  * MCX options on different expiries are written on DIFFERENT futures contracts (the option row's
    `underlying_key`), so one fixed futures key per commodity is wrong.
  * Index spot has no traded volume/OI: volume, VWAP and OI buildup must come from the near-month
    index FUTURE, whose key rolls every month.
  * Lot sizes change (NSE reviews them twice a year); MCX quantities are in `qty_multiplier` units
    (GOLD: lot_size=1 but qty_multiplier=100).
"""

import asyncio
import gzip
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.core.logging.logger import logger

FILE_URL = "https://assets.upstox.com/market-quote/instruments/exchange/{exchange}.json.gz"
_IST = ZoneInfo("Asia/Kolkata")
# MCX file is small and new contracts appear intraday: hourly. NSE/BSE files are large: once a day.
_REFRESH_SECONDS = {"MCX": 3600, "NSE": 6 * 3600, "BSE": 6 * 3600}
_SEGMENT = {"MCX": "MCX_FO", "NSE": "NSE_FO", "BSE": "BSE_FO"}


@dataclass(frozen=True)
class OptionContract:
    key: str
    underlyingKey: str  # the futures (MCX) or index (NSE/BSE) the option is written on
    side: str  # CE | PE
    strike: float
    expiry: str  # YYYY-MM-DD (IST)
    lotUnits: int  # quantity per lot in premium units
    symbol: str


@dataclass(frozen=True)
class FutureContract:
    key: str
    expiry: str
    lotUnits: int
    symbol: str


def _ist_date(ms: Any) -> str | None:
    try:
        v = int(ms)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return datetime.fromtimestamp(v / 1000, _IST).strftime("%Y-%m-%d")


def _units(row: dict[str, Any], exchange: str) -> int:
    """Premium units per lot. MCX uses qty_multiplier (GOLD lot_size=1, qty_multiplier=100)."""
    raw = row.get("qty_multiplier") if exchange == "MCX" else row.get("lot_size")
    try:
        v = float(raw or 0)
    except (TypeError, ValueError):
        return 0
    if exchange == "MCX" and v <= 0:
        v = float(row.get("lot_size") or 0)
    return int(v) if v > 0 and v == int(v) else 0


def parse_rows(rows: list[dict[str, Any]], exchange: str) -> tuple[dict[str, list[OptionContract]], dict[str, list[FutureContract]]]:
    """Pure parser (unit-tested): {SYMBOL: [options]}, {SYMBOL: [futures]} for one exchange file."""
    seg = _SEGMENT[exchange]
    options: dict[str, list[OptionContract]] = {}
    futures: dict[str, list[FutureContract]] = {}
    for row in rows:
        if row.get("segment") != seg:
            continue
        itype = row.get("instrument_type")
        name = (row.get("underlying_symbol") or row.get("name") or "").upper().replace(" ", "")
        expiry = _ist_date(row.get("expiry"))
        key = row.get("instrument_key") or ""
        units = _units(row, exchange)
        if not name or not expiry or not key or units <= 0:
            continue
        if itype in ("CE", "PE"):
            try:
                strike = float(row.get("strike_price") or 0)
            except (TypeError, ValueError):
                continue
            ukey = row.get("underlying_key") or ""
            if strike <= 0 or not ukey:
                continue
            options.setdefault(name, []).append(
                OptionContract(key, ukey, itype, strike, expiry, units, row.get("trading_symbol") or "")
            )
        elif itype == "FUT":
            futures.setdefault(name, []).append(FutureContract(key, expiry, units, row.get("trading_symbol") or ""))
    for v in options.values():
        v.sort(key=lambda c: (c.expiry, c.strike, c.side))
    for f in futures.values():
        f.sort(key=lambda c: c.expiry)
    return options, futures


class InstrumentCatalog:
    def __init__(self) -> None:
        self._options: dict[str, dict[str, list[OptionContract]]] = {}
        self._futures: dict[str, dict[str, list[FutureContract]]] = {}
        self._loaded_at: dict[str, float] = {}
        self._day: dict[str, str] = {}
        self._locks = {ex: asyncio.Lock() for ex in _SEGMENT}

    async def _ensure(self, exchange: str) -> None:
        today = datetime.now(_IST).strftime("%Y-%m-%d")
        fresh = (
            self._day.get(exchange) == today
            and time.monotonic() - self._loaded_at.get(exchange, 0) < _REFRESH_SECONDS[exchange]
        )
        if fresh:
            return
        async with self._locks[exchange]:
            if self._day.get(exchange) == today and time.monotonic() - self._loaded_at.get(exchange, 0) < _REFRESH_SECONDS[exchange]:
                return
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    r = await client.get(FILE_URL.format(exchange=exchange))
                    r.raise_for_status()
                rows = await asyncio.to_thread(lambda: json.loads(gzip.decompress(r.content)))
                options, futures = await asyncio.to_thread(parse_rows, rows, exchange)
                if not options and not futures:
                    raise ValueError(f"no {_SEGMENT[exchange]} contracts in the file")
                self._options[exchange], self._futures[exchange] = options, futures
                self._loaded_at[exchange], self._day[exchange] = time.monotonic(), today
                logger.info(f"[INSTRUMENTS] {exchange} loaded: {len(options)} option underlyings, {len(futures)} futures")
            except Exception as e:
                logger.warning(f"[INSTRUMENTS_UNAVAILABLE] {exchange}: {type(e).__name__}: {e}")
                if exchange not in self._options:
                    raise
                # keep the previous (same-day or older) catalogue and retry on the next call

    @staticmethod
    def _today() -> str:
        return datetime.now(_IST).strftime("%Y-%m-%d")

    async def options(self, exchange: str, symbol: str) -> list[OptionContract]:
        """All live option contracts (expiry today or later) for one underlying, sorted by expiry/strike."""
        await self._ensure(exchange)
        today = self._today()
        return [c for c in self._options.get(exchange, {}).get(symbol.upper(), []) if c.expiry >= today]

    async def option_expiries(self, exchange: str, symbol: str) -> list[str]:
        return sorted({c.expiry for c in await self.options(exchange, symbol)})

    async def near_future(self, exchange: str, symbol: str, roll_on_expiry_day: bool = True) -> FutureContract | None:
        """Near-month future. On its own expiry day the next month is used (expiring futures distort OI/volume)."""
        await self._ensure(exchange)
        today = self._today()
        live = [f for f in self._futures.get(exchange, {}).get(symbol.upper(), []) if f.expiry >= today]
        if roll_on_expiry_day and len(live) > 1 and live[0].expiry == today:
            return live[1]
        return live[0] if live else None

    async def lot_units(self, exchange: str, symbol: str) -> int | None:
        opts = await self.options(exchange, symbol)
        return opts[0].lotUnits if opts else None


instrument_catalog = InstrumentCatalog()
