import gzip
import json
from datetime import datetime
from typing import Any

import httpx

MCX_INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz"


class McxInstrumentResolver:
    """
    MCX option chains hang off the nearest futures contract, which rolls every month.
    Finds that futures instrument key from Upstox's public instrument file, cached per day.
    """

    def __init__(self) -> None:
        self._day: str | None = None
        self._futures: dict[str, dict[str, Any]] = {}

    async def _load(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if self._day == today and self._futures:
            return
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(MCX_INSTRUMENTS_URL)
            r.raise_for_status()
        rows = json.loads(gzip.decompress(r.content))
        now_ms = datetime.now().timestamp() * 1000
        best: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row.get("segment") != "MCX_FO" or row.get("instrument_type") != "FUT":
                continue
            name = (row.get("underlying_symbol") or row.get("name") or "").upper()
            exp = row.get("expiry") or 0
            if exp < now_ms:
                continue
            if name not in best or exp < best[name]["expiry"]:
                best[name] = {"key": row["instrument_key"], "expiry": exp, "lotSize": row.get("lot_size")}
        self._day, self._futures = today, best

    async def resolve(self, code: str) -> dict[str, Any] | None:
        await self._load()
        return self._futures.get(code.upper())


mcx_resolver = McxInstrumentResolver()
