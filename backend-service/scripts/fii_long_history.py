"""FII_OPEN_DRIVE long-history test with controls (18 Nov 2026 research review, item 2).

Question: does "FII index-futures net long rose yesterday" predict the 09:21 -> 10:30 move on more than the 6 months
it was found on -- and does it beat the obvious controls (prior day up, gap up)? If it doesn't beat them, the FII data
adds nothing. Underlying only (no option pricing): the setup buys an ITM CE, so the index move decides it.

Run inside the backend container (it has NSE + Upstox access; first run downloads ~1,100 NSE files, ~10 min):
    docker exec -i autotrader_backend python - < backend-service/scripts/fii_long_history.py
Optional: FROM=2022-01-01 CODES=NIFTY,BANKNIFTY,SENSEX (env vars). Upstox 1-minute history starts Jan 2022.
Report: logs/fii_long_history.txt (also printed).

PASS (from the review): positive mean in both halves AND in >= 70% of calendar years, beats both controls, t >= 2 at
the DAY level (indices averaged: one bet per day). A FAIL means: keep FII_OPEN_DRIVE at probation size.
"""
import asyncio
import math
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, "/app")
from app.core.db.session import async_session_factory  # noqa: E402
from app.modules.opportunity_finder.provider.underlying_config import get_config  # noqa: E402
from app.modules.opportunity_finder.provider.upstox_market_data import market_data  # noqa: E402
from app.modules.opportunity_finder.service import fii_open  # noqa: E402
from app.modules.opportunity_finder.service import positioning as pos  # noqa: E402

START = date.fromisoformat(os.environ.get("FROM", "2022-01-01"))
CODES = [c.strip().upper() for c in os.environ.get("CODES", "NIFTY,BANKNIFTY,SENSEX").split(",") if c.strip()]
OUT = Path("/app/logs/fii_long_history.txt") if Path("/app/logs").exists() else Path("fii_long_history.txt")
lines: list[str] = []


def say(s: str) -> None:
    print(s, flush=True)
    lines.append(s)


async def fetch_positioning() -> None:
    d, got = START - timedelta(days=10), 0
    while d <= date.today():
        if d.weekday() < 5 and await pos.fetch(d):
            got += 1
            await asyncio.sleep(0.3)  # be gentle with NSE archives
        d += timedelta(days=1)
    say(f"participant OI files available: {got}")


def stats(name: str, rows: list[dict]) -> dict | None:
    xs = [r["move"] for r in rows]
    if len(xs) < 2:
        say(f"{name:44s} n={len(xs)}")
        return None
    n, m = len(xs), sum(xs) / len(xs)
    sd = (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5
    t = m / (sd / math.sqrt(n)) if sd else 0.0
    hit = sum(x > 0 for x in xs) / n * 100
    say(f"{name:44s} n={n:5d} hit={hit:5.1f}% mean={m:+.3f}% t={t:+.2f}")
    return {"n": n, "mean": m, "t": t}


async def main() -> None:
    await fetch_positioning()
    rows: list[dict] = []
    async with async_session_factory() as s:
        for code in CODES:
            cfg = get_config(code)
            say(f"fetching {code} 1-minute candles {START} .. today")
            bars = await market_data.history_span(cfg.instrumentKey, "minutes/1", START.isoformat(),
                                                  date.today().isoformat(), s)
            by_day: dict[str, list[dict]] = defaultdict(list)
            for b in bars:
                by_day[b["t"][:10]].append(b)
            days = sorted(d for d, v in by_day.items() if len(v) > 300)
            for p, d in zip(days, days[1:]):
                bm = {b["t"][11:16]: b for b in by_day[d]}
                if "09:21" not in bm or "10:29" not in bm:
                    continue
                ch = fii_open.fii_net_change(date.fromisoformat(d))
                if ch is None:
                    continue
                prev = by_day[p]
                o, c = bm["09:21"]["o"], bm["10:29"]["c"]
                rows.append({"code": code, "d": d, "move": (c - o) / o * 100, "fii": ch[0],
                             "prev": (prev[-1]["c"] - prev[0]["o"]) / prev[0]["o"] * 100,
                             "gap": (by_day[d][0]["o"] - prev[-1]["c"]) / prev[-1]["c"] * 100})
    if not rows:
        say("no rows: check the Upstox token and the participant OI download")
        return
    # one bet per day: average the indices
    by_d: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_d[r["d"]].append(r)
    day_rows = [{"d": d, "move": sum(x["move"] for x in v) / len(v), "fii": v[0]["fii"],
                 "prev": sum(x["prev"] for x in v) / len(v), "gap": sum(x["gap"] for x in v) / len(v)}
                for d, v in sorted(by_d.items())]
    say(f"\nrange {day_rows[0]['d']} .. {day_rows[-1]['d']} · {len(day_rows)} days · {', '.join(CODES)}")
    say("== long 09:21 -> 10:30, index % move, one bet per day ==")
    base = stats("all days (always long)", day_rows)
    fii = stats("FII net long UP (the live signal)", [r for r in day_rows if r["fii"] > 0])
    c1 = stats("control: prior day UP", [r for r in day_rows if r["prev"] > 0])
    c2 = stats("control: gap UP", [r for r in day_rows if r["gap"] > 0])
    stats("FII UP & prior day DOWN", [r for r in day_rows if r["fii"] > 0 and r["prev"] <= 0])
    stats("FII DOWN (PE mirror would short this)", [r for r in day_rows if r["fii"] <= 0])
    mid = day_rows[len(day_rows) // 2]["d"]
    sig = [r for r in day_rows if r["fii"] > 0]
    h1 = stats(f"FII UP, first half (< {mid})", [r for r in sig if r["d"] < mid])
    h2 = stats(f"FII UP, second half (>= {mid})", [r for r in sig if r["d"] >= mid])
    years = sorted({r["d"][:4] for r in sig})
    pos_years = 0
    for y in years:
        st = stats(f"FII UP, {y}", [r for r in sig if r["d"].startswith(y)])
        pos_years += bool(st and st["mean"] > 0)
    checks = {
        "both halves positive": bool(h1 and h2 and h1["mean"] > 0 and h2["mean"] > 0),
        f">= 70% of years positive ({pos_years}/{len(years)})": len(years) > 0 and pos_years / len(years) >= 0.7,
        "beats prior-day control": bool(fii and c1 and fii["mean"] > c1["mean"]),
        "beats gap control": bool(fii and c2 and fii["mean"] > c2["mean"]),
        "beats always-long": bool(fii and base and fii["mean"] > base["mean"]),
        "t >= 2 at day level": bool(fii and fii["t"] >= 2),
    }
    say("\n== gate ==")
    for k, v in checks.items():
        say(f"  {'PASS' if v else 'FAIL'}  {k}")
    say("VERDICT: " + ("PASS -- FII_OPEN_DRIVE holds on the long history" if all(checks.values())
                       else "FAIL -- keep FII_OPEN_DRIVE at probation size (1 lot, its 5% budget only)"))
    OUT.write_text("\n".join(lines) + "\n")
    print(f"\nreport written to {OUT}")


asyncio.run(main())
