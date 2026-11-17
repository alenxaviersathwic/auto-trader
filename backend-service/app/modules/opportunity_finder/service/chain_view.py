"""
Option-chain (OI) picture around one strike, built ONLY from recorded chain snapshots (option_chain_snapshots,
written by chain_recorder.py about every 15 s while the engine runs). Nothing here is estimated: when there is no
recent snapshot the answer is None and the UI says so.

Used by the live trade view (trades module) to show the real Call / Put OI ladder next to a running trade.
"""
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.opportunity_finder.repository.opportunity_repository import option_chain_snapshot_repository

MAX_SNAPSHOT_AGE_S = 300     # a chain older than 5 minutes is not shown as "live"
CHANGE_LOOKBACK_MIN = 15     # OI change is measured against the snapshot from about 15 minutes earlier
LADDER_EACH_SIDE = 3         # strikes shown above and below the traded strike
SOURCE = "CHAIN_SNAPSHOT"
# packed row: [strike, ceLtp, ceOi, ceVol, ceBid, ceAsk, ceDelta, ceIv, peLtp, peOi, peVol, ...] (see OptionChainSnapshot)
_STRIKE, _CE_OI, _CE_VOL, _PE_OI, _PE_VOL = 0, 2, 3, 9, 10


def _rows(strikes: list[Any]) -> dict[float, dict[str, float]]:
    out: dict[float, dict[str, float]] = {}
    for r in strikes or []:
        if isinstance(r, list) and len(r) > _PE_VOL:
            out[float(r[_STRIKE])] = {"callOi": float(r[_CE_OI] or 0), "putOi": float(r[_PE_OI] or 0),
                                      "vol": float(r[_CE_VOL] or 0) + float(r[_PE_VOL] or 0)}
    return out


def _chg(now: float, before: float | None) -> float | None:
    return round((now - before) / before * 100, 1) if before else None


def max_pain(rows: dict[float, dict[str, float]]) -> float | None:
    """Strike where option buyers lose the most at expiry (the lowest total intrinsic value owed by writers)."""
    if not rows:
        return None
    ks = sorted(rows)
    return min(ks, key=lambda k: sum(rows[s]["callOi"] * max(0.0, k - s) + rows[s]["putOi"] * max(0.0, s - k)
                                     for s in ks))


def build(strike: float, option_type: str, cur: dict[str, Any], prev: dict[str, Any] | None) -> dict[str, Any] | None:
    """`cur` / `prev` = {"spot", "pcr", "strikes" (packed rows), "at" (datetime)}. Pure: easy to unit-test."""
    rows = _rows(cur.get("strikes") or [])
    if not rows:
        return None
    before = _rows(prev.get("strikes") or []) if prev else {}
    ks = sorted(rows)
    spot = float(cur.get("spot") or 0)
    centre = min(range(len(ks)), key=lambda i: abs(ks[i] - float(strike)))
    ladder = ks[max(0, centre - LADDER_EACH_SIDE): centre + LADDER_EACH_SIDE + 1]
    calls_above = [k for k in ks if k >= spot] or ks
    puts_below = [k for k in ks if k <= spot] or ks
    call_wall = max(calls_above, key=lambda k: rows[k]["callOi"])
    put_wall = max(puts_below, key=lambda k: rows[k]["putOi"])
    avg_vol = sum(rows[k]["vol"] for k in ladder) / len(ladder) or 1.0
    tot_ce = sum(r["callOi"] for r in rows.values())
    tot_pe = sum(r["putOi"] for r in rows.values())
    b_ce = sum(r["callOi"] for r in before.values()) if before else None
    b_pe = sum(r["putOi"] for r in before.values()) if before else None
    ce_chg, pe_chg = _chg(tot_ce, b_ce), _chg(tot_pe, b_pe)
    ce = option_type.upper() == "CE"
    if ce_chg is None or pe_chg is None:
        buildup, flow = "NO_HISTORY", "no earlier snapshot to measure OI change against"
    else:
        buildup = ("PUT_WRITING" if pe_chg > ce_chg else "CALL_WRITING") if abs(pe_chg - ce_chg) >= 0.5 else "BALANCED"
        helps = (buildup == "PUT_WRITING") if ce else (buildup == "CALL_WRITING")
        flow = (f"call OI {ce_chg:+.1f}%, put OI {pe_chg:+.1f}% in {CHANGE_LOOKBACK_MIN} min: "
                + ("supports" if helps else "neutral for" if buildup == "BALANCED" else "works against")
                + f" this {option_type.upper()}")
    pcr = cur.get("pcr")
    pcr = round(float(pcr), 2) if pcr is not None else (round(tot_pe / tot_ce, 2) if tot_ce else None)
    at: datetime = cur["at"]
    return {
        "source": SOURCE,
        "asOf": at.isoformat(),
        "spot": round(spot, 2),
        "pcr": pcr,
        "maxPain": max_pain(rows),
        "putOiSupportWall": put_wall,
        "callOiResistanceWall": call_wall,
        "oiBuildup": buildup,
        "verdict": f"Put-OI wall {put_wall:,.0f}, call-OI wall {call_wall:,.0f}, PCR {pcr}; {flow}.",
        "strikes": [
            {
                "strike": k, "callOi": int(rows[k]["callOi"]), "putOi": int(rows[k]["putOi"]),
                "callOiChgPct": _chg(rows[k]["callOi"], (before.get(k) or {}).get("callOi")),
                "putOiChgPct": _chg(rows[k]["putOi"], (before.get(k) or {}).get("putOi")),
                "volumeRatio": round(rows[k]["vol"] / avg_vol, 2),
                "role": ("ACTIVE_STRIKE" if k == ks[centre] else "CALL_OI_WALL" if k == call_wall
                         else "PUT_OI_WALL" if k == put_wall else "CHAIN"),
            }
            for k in ladder
        ],
    }


async def oa_analysis(session: AsyncSession, code: str, expiry: str, option_type: str, strike: float,
                      now: datetime | None = None) -> dict[str, Any] | None:
    """Real OI ladder for one contract from the newest snapshot, or None when none is recent enough."""
    now = now or datetime.now(UTC)
    cur = await option_chain_snapshot_repository.latest(session, code, expiry, now - timedelta(seconds=MAX_SNAPSHOT_AGE_S))
    if cur is None:
        return None
    prev = await option_chain_snapshot_repository.latest_before(
        session, code, expiry, cur.createdAt - timedelta(minutes=CHANGE_LOOKBACK_MIN),
        cur.createdAt - timedelta(minutes=3 * CHANGE_LOOKBACK_MIN))

    def view(r: Any) -> dict[str, Any]:
        return {"spot": float(r.spot or 0), "pcr": r.pcr, "strikes": r.strikes, "at": r.createdAt}

    return build(strike, option_type, view(cur), view(prev) if prev is not None else None)
