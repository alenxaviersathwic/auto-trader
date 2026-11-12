#!/usr/bin/env python3
"""
Does the dealer-gamma proxy actually separate momentum from mean reversion on OUR data? (institutional review,
Strategy 3: "ship only if the negative-GEX tercile shows significantly higher continuation, t > 2").

For every recorded option-chain snapshot (option_chain_snapshots, nearest expiry, 15-s cadence from 11 Nov 2026):
  gex      gamma_regime.net_gex() on that snapshot (default sign convention, or --participant to use the NSE client book
           of the snapshot's day)
  cont     continuation = sign(spot_t - spot_{t-30m}) x (spot_{t+30m} - spot_t) / spot_t   (positive = momentum)
Snapshots are split into GEX terciles per underlying; the script prints mean continuation per tercile and Welch's
t-stat of NEGATIVE vs POSITIVE. If t > 2, set GAMMA_ROUTER_ENABLED=true in .env.

  PYTHONPATH=. python scripts/validate_gamma_regime.py --codes NIFTY SENSEX --days 60
"""
import argparse
import asyncio
import bisect
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select  # noqa: E402

from app.core.db.session import async_session_factory  # noqa: E402
from app.modules.opportunities.entity.opportunity_entity import OptionChainSnapshot  # noqa: E402
from app.modules.opportunities.service import gamma_regime as gr, positioning  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
HORIZON = timedelta(minutes=30)
COLS = ("ltp", "oi", "volume", "bid", "ask", "delta", "iv")


def _chain(snap: OptionChainSnapshot) -> dict:
    rows = []
    for r in snap.strikes or []:
        ce = dict(zip(COLS, r[1:8]))
        pe = dict(zip(COLS, r[8:15]))
        rows.append({"strike": r[0], "CE": ce, "PE": pe})
    return {"expiry": snap.expiry, "strikes": rows}


def _welch(a: list[float], b: list[float]) -> float | None:
    if len(a) < 10 or len(b) < 10:
        return None
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
    vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
    se = math.sqrt(va / len(a) + vb / len(b))
    return (ma - mb) / se if se > 0 else None


async def run(codes: list[str], days: int, use_participant: bool) -> None:
    since = datetime.now(UTC) - timedelta(days=days)
    async with async_session_factory() as s:
        for code in codes:
            rows = (await s.execute(select(OptionChainSnapshot).where(OptionChainSnapshot.underlyingCode == code)
                                    .where(OptionChainSnapshot.createdAt >= since)
                                    .order_by(OptionChainSnapshot.createdAt))).scalars().all()
            by_t: dict[datetime, OptionChainSnapshot] = {}
            for r in rows:  # nearest expiry per timestamp
                t = r.createdAt.replace(microsecond=0)
                if t not in by_t or r.expiry < by_t[t].expiry:
                    by_t[t] = r
            ts = sorted(by_t)
            spots = [float(by_t[t].spot) for t in ts]
            pts: list[tuple[float, float]] = []
            for i, t in enumerate(ts):
                j0 = bisect.bisect_left(ts, t - HORIZON)
                j1 = bisect.bisect_left(ts, t + HORIZON)
                if j0 >= i or j1 >= len(ts) or ts[j1].date() != t.date() or ts[j0].date() != t.date():
                    continue
                past, fut = spots[i] - spots[j0], spots[j1] - spots[i]
                if past == 0:
                    continue
                signs = (1, -1)
                if use_participant:
                    p = positioning.snapshot(t.astimezone(IST).date())
                    signs = gr.participant_signs(p.get("client"))
                gex = gr.net_gex(_chain(by_t[t]), spots[i], t.astimezone(IST), *signs)
                pts.append((gex, math.copysign(1, past) * fut / spots[i] * 1e4))  # bp
            if len(pts) < 90:
                print(f"{code}: only {len(pts)} usable snapshots -- keep recording")
                continue
            g = sorted(p[0] for p in pts)
            lo, hi = g[len(g) // 3], g[2 * len(g) // 3]
            neg = [c for x, c in pts if x <= lo]
            mid = [c for x, c in pts if lo < x < hi]
            pos_ = [c for x, c in pts if x >= hi]
            t = _welch(neg, pos_)
            fmt = lambda v: f"{sum(v) / len(v):+.2f}bp (n={len(v)})" if v else "-"  # noqa: E731
            print(f"{code}: continuation NEG {fmt(neg)} | MID {fmt(mid)} | POS {fmt(pos_)} | t(NEG-POS) = "
                  f"{t:.2f}" if t is not None else f"{code}: not enough points per tercile")
            if t is not None:
                print(f"   -> {'ENABLE the router (t > 2)' if t > 2 else 'keep GAMMA_ROUTER_ENABLED=false'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--codes", nargs="+", default=["NIFTY", "SENSEX"])
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--participant", action="store_true", help="sign convention from NSE client option book")
    a = ap.parse_args()
    asyncio.run(run(a.codes, a.days, a.participant))
