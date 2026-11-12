#!/usr/bin/env python3
"""
Expiry-day IRON FLY replay (app/modules/opportunities/service/iron_fly.py) over the days we have index candles for.
Legs are priced from REAL 1-minute option candles in backtest_data/ when all four exist (bid/ask approximated as
candle price -/+ REAL_HALF_SPREAD_PCT), otherwise from Black-Scholes at a fixed IV -- and on expiry day a fixed IV is
exactly the model the research says is wrong (theta collapse, smile), so BS rows are labelled and are NOT evidence.

  PYTHONPATH=. python scripts/backtest_iron_fly.py

Only days that ARE the underlying's expiry are traded. Add new days by adding a day_data_*.py module to DAYS.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_day as bd  # noqa: E402
import day_data as d9  # noqa: E402
import day_data_fri as d6  # noqa: E402
import day_data_wed as d11  # noqa: E402
from app.modules.opportunities.provider.underlying_config import get_config  # noqa: E402
from app.modules.opportunities.service import iron_fly as fly  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
# (day, {code: packed 1-min candles}, daily seed, {code: expiry of the series traded that day})
DAYS = [
    ("2026-11-06", {"NIFTY": d6.FRI_NIFTY, "SENSEX": d6.FRI_SENSEX, "BANKNIFTY": d6.FRI_BANKNIFTY}, d6.FRI_DAILY,
     {"NIFTY": "2026-11-09", "SENSEX": "2026-11-12", "BANKNIFTY": "2026-11-23"}),
    ("2026-11-09", {"NIFTY": d9.NIFTY, "SENSEX": d9.SENSEX, "BANKNIFTY": d9.BANKNIFTY}, d9.DAILY,
     {"NIFTY": "2026-11-09", "SENSEX": "2026-11-12", "BANKNIFTY": "2026-11-23"}),
    ("2026-11-11", {"NIFTY": d11.WED_NIFTY, "SENSEX": d11.WED_SENSEX, "BANKNIFTY": d11.WED_BANKNIFTY}, d11.WED_DAILY,
     {"NIFTY": "2026-11-17", "SENSEX": "2026-11-12", "BANKNIFTY": "2026-11-23"}),
]


def _quote(code, strike, side, minute, spot, real):
    """(bid, ask) at `minute` from real candles (close +- half spread) or Black-Scholes."""
    if real is not None:
        b = real.get((side, strike), {}).get(minute)
        if b is None:
            return None
        px = b["c"]
    else:
        px = bd.bs(code, spot, strike, minute, side == "CE")[0]
    h = px * bd.REAL_HALF_SPREAD_PCT / 100
    return max(0.05, px - h), px + h


def run_day(day, packed, daily, expiry):
    bd.DAY, bd.EXPIRY = day, expiry
    out = []
    for code, s in packed.items():
        if expiry[code] != day:
            continue
        cfg = get_config(code)
        bars = bd.decode(s, day)
        pdc = daily[code][-1][4]
        gap = (bars[0]["o"] - pdc) / pdc * 100
        # the replay modules carry 3 daily bars and no VIX history: the VRP / VIX-percentile gates cannot be evaluated
        # here, so they are ASSUMED to pass (labelled in the output) -- the live paper engine applies them for real
        a = {"dte": 0, "levels": {"gapPct": round(gap, 2)}, "vix": {}, "dayType": {},
             "vrpRatio": fly.vrp_ratio(None, []) or fly.MIN_VRP_RATIO, "vixPctile": 50.0}
        for k, b in enumerate(bars):
            m = int(b["t"][11:13]) * 60 + int(b["t"][14:16])
            now = datetime.fromisoformat(b["t"])
            ok, why = fly.eligible(a, now)
            if not ok:
                if now.time() > fly.ENTRY_TO or "gap" in " ".join(why):
                    out.append((day, code, "SKIP", "; ".join(why), 0.0, "-"))
                    break
                continue
            spot = b["c"]
            atm = round(spot / cfg.strikeStep) * cfg.strikeStep
            strikes = [atm + i * cfg.strikeStep for i in range(-10, 11)]
            reals = {(sd, k2): bd.real_bars(code, k2, sd == "CE") for sd in ("CE", "PE") for k2 in strikes}
            real = None if any(v is None for v in reals.values()) else {k3: v for k3, v in reals.items()}
            chain = {"expiry": expiry[code], "strikes": []}
            for k2 in strikes:
                row = {"strike": k2}
                for sd in ("CE", "PE"):
                    q = _quote(code, k2, sd, m, spot, real)
                    row[sd] = {"bid": q[0], "ask": q[1]} if q else {"bid": 0, "ask": 0}
                chain["strikes"].append(row)
            f, why_b = fly.build(chain, spot, cfg.strikeStep, cfg.lotSize, code, cfg.exchange, gap)
            if not f:
                out.append((day, code, "SKIP", why_b, 0.0, "-"))
                break
            exit_reason, val = "EOD", f.credit
            for j2, b2 in enumerate(bars[k + 1:], start=k + 1):
                m2 = int(b2["t"][11:13]) * 60 + int(b2["t"][14:16])
                px = {}
                for act, sd, k2, _p, _key in f.legs:
                    q = _quote(code, k2, sd, m2, b2["c"], real)
                    if q:
                        px[(sd, k2)] = q[1] if act == "SELL" else q[0]  # buy back shorts at ask, sell wings at bid
                if len(px) < 4:
                    continue
                val = fly.fly_value(px, f)
                c5 = bars[j2]["c"] if (j2 + 1) % 5 == 0 else None  # a 5-minute bar just completed
                r = fly.check_exit(f, val, datetime.fromisoformat(b2["t"]), c5)
                if r:
                    exit_reason = r
                    break
            src = "REAL" if real else "BS*"
            out.append((day, code, exit_reason, f"{now:%H:%M} ATM {f.atm:.0f} wings {f.putWing:.0f}/{f.callWing:.0f} "
                        f"credit {f.credit:.1f} -> {val:.1f}", fly.pnl_rs(f, val), src))
            break
    return out


def main():
    rows = [r for d in DAYS for r in run_day(*d)]
    if not rows:
        print("no expiry days in the loaded data")
    for day, code, res, txt, pnl, src in rows:
        print(f"{day} {code:<9} {res:<11} {src:<4} {txt}  net Rs {pnl:+,.0f}")
    print(f"\nTOTAL net Rs {sum(r[4] for r in rows):+,.0f} over {sum(1 for r in rows if r[2] != 'SKIP')} fly(s)")
    print("BS* = Black-Scholes at a fixed IV: on expiry day this is NOT evidence -- download real candles first.")
    print("VRP / VIX-percentile gates are ASSUMED to pass in this replay (no IV / VIX history in the day modules).")


if __name__ == "__main__":
    main()
