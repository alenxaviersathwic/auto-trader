"""Records the option chain the engine just read (option_chain_snapshots), at most once per SNAPSHOT_EVERY_S per
underlying. Best effort: a failed write never touches the iteration. See OptionChainSnapshot for why it exists."""
import time
from typing import Any

from app.core.db.session import async_session_factory
from app.core.logging.logger import logger
from app.modules.opportunities.entity.opportunity_entity import OptionChainSnapshot

# 11 Nov 2026 research review (gap 2): this table becomes the proprietary fill / spread dataset, so record densely.
# ~15 s x 6 underlyings x 2 expiries is ~25-30 MB/day of JSONB; prune or archive monthly.
SNAPSHOT_EVERY_S = 15.0
_LEG = ("ltp", "oi", "volume", "bid", "ask", "delta", "iv")
_QTY = ("bidQty", "askQty")  # appended AFTER the 15 original columns so older readers keep working
_last: dict[str, float] = {}


def pack(chain: dict[str, Any]) -> list[list[float]]:
    """Chain strikes -> compact rows (column order documented on the entity)."""
    return [[s["strike"]] + [s[side].get(k) or 0 for side in ("CE", "PE") for k in _LEG]
            + [s[side].get(k) or 0 for side in ("CE", "PE") for k in _QTY] for s in chain.get("strikes") or []]


def due(code: str, now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    return now - _last.get(code, -1e9) >= SNAPSHOT_EVERY_S


async def record(code: str, market: dict[str, Any]) -> int:
    """Rows written (one per expiry in the market fetch), 0 when throttled, empty or failed."""
    chains = [c for c in market.get("chains") or [] if c.get("strikes")]
    if not chains or not due(code):
        return 0
    _last[code] = time.monotonic()
    vix = (market.get("vix") or {}).get("value") if isinstance(market.get("vix"), dict) else None
    try:
        async with async_session_factory() as s:
            for c in chains:
                s.add(OptionChainSnapshot(underlyingCode=code, expiry=c["expiry"], spot=market.get("spot") or 0,
                                          pcr=c.get("pcr"), atmStraddle=c.get("atmStraddle"), vix=vix, strikes=pack(c)))
            await s.commit()
        return len(chains)
    except Exception as e:
        logger.warning(f"[CHAIN_SNAPSHOT] {code}: {type(e).__name__}: {e}")
        return 0
