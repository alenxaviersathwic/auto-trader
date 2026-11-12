#!/usr/bin/env python3
"""
Download ~1 month of REAL Upstox data for the month replay (scripts/backtest_month_real.py):
  * index 1-minute candles (NIFTY, BANKNIFTY, SENSEX) + 4 months of daily candles
  * 1-minute candles of every CE/PE strike near the traded range, for every expiry that was the current or next
    series during the month -- live series through the normal historical API, expired series through the Upstox Plus
    "Expired Instruments" API (skipped, and reported, if the account doesn't have it)

Run it INSIDE the backend container (it reuses the Upstox login stored in the DB); files land in the shared logs/
folder:
    docker exec -i autotrader_backend python - < backend-service/scripts/fetch_month_real.py
Takes ~5-10 minutes. Re-running skips files that already exist.
"""
import asyncio
import csv
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import httpx

sys.path.insert(0, "/app")
OUT = Path(os.environ.get("REALDATA_DIR", "/app/logs/realdata"))
API = "https://api.upstox.com"
CODES = {"NIFTY": ("NSE_INDEX|Nifty 50", 50.0), "BANKNIFTY": ("NSE_INDEX|Nifty Bank", 100.0),
         "SENSEX": ("BSE_INDEX|SENSEX", 100.0)}
DAYS_BACK = 31
PAD_STEPS = 8
# days before expiry a series can be the current/next one: weeklies ~2 weeks, the MONTHLY-only BANKNIFTY ~5 weeks
SERIES_WINDOW = {"NIFTY": 21, "SENSEX": 21, "BANKNIFTY": 40}
CONC = 5
TODAY = date.today()
START = TODAY - timedelta(days=DAYS_BACK)
stats = {"requests": 0, "errors": [], "contracts": 0, "expiredApi": None}


async def token() -> str:
    if os.environ.get("UPSTOX_ACCESS_TOKEN"):
        return os.environ["UPSTOX_ACCESS_TOKEN"]
    from app.core.db.session import async_session_factory
    from app.modules.opportunities.provider.upstox_market_data import market_data

    async with async_session_factory() as s:
        return await market_data._token(s)


async def get(c: httpx.AsyncClient, sem: asyncio.Semaphore, url: str, **params):
    async with sem:
        for attempt in range(4):
            r = await c.get(url, params=params or None)
            stats["requests"] += 1
            if r.status_code == 429:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            await asyncio.sleep(0.12)
            if r.status_code != 200:
                raise RuntimeError(f"{r.status_code} {url.split('?')[0][-90:]}: {r.text[:160]}")
            return (r.json() or {}).get("data")
        raise RuntimeError(f"429 rate-limited: {url[-90:]}")


def write(f: Path, rows) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "open", "high", "low", "close", "volume", "oi"])
        w.writerows(sorted(rows))


async def candles_v3(c, sem, key, unit, n, frm: date, to: date):
    k = quote(key, safe="")
    d = await get(c, sem, f"{API}/v3/historical-candle/{k}/{unit}/{n}/{to}/{frm}")
    return (d or {}).get("candles") or []


async def index_data(c, sem):
    rng = {}
    for code, (key, step) in CODES.items():
        rows = await candles_v3(c, sem, key, "minutes", 1, START, TODAY)
        try:
            k = quote(key, safe="")
            intr = await get(c, sem, f"{API}/v3/historical-candle/intraday/{k}/minutes/1")
            have = {r[0] for r in rows}
            rows += [r for r in (intr or {}).get("candles") or [] if r[0] not in have]
        except Exception as e:  # noqa: BLE001
            stats["errors"].append(f"{code} intraday: {e}")
        write(OUT / "index" / f"{code}.csv", rows)
        daily = await candles_v3(c, sem, key, "days", 1, START - timedelta(days=120), TODAY)
        write(OUT / "daily" / f"{code}.csv", daily)
        by_day: dict[str, list[float]] = {}
        for r in rows:
            by_day.setdefault(r[0][:10], []).extend([r[2], r[3]])
        rng[code] = {d: (min(v), max(v)) for d, v in by_day.items()}
        print(f"{code}: {len(rows)} 1-min bars over {len(by_day)} days, {len(daily)} daily bars", flush=True)
    try:  # India VIX, 1 year daily: the iron fly's VIX-percentile gate
        vix = await candles_v3(c, sem, "NSE_INDEX|India VIX", "days", 1, TODAY - timedelta(days=380), TODAY)
        write(OUT / "daily" / "INDIAVIX.csv", vix)
    except Exception as e:  # noqa: BLE001
        stats["errors"].append(f"India VIX daily: {e}")
    return rng


async def series(c, sem, code, key):
    """{expiry: [contract dicts]} for live + expired series that matter for START..TODAY+14."""
    out: dict[str, list] = {}
    live = await get(c, sem, f"{API}/v2/option/contract", instrument_key=key) or []
    for x in live:
        if x["expiry"] <= (TODAY + timedelta(days=21)).isoformat():
            out.setdefault(x["expiry"], []).append({**x, "_expired": False})
    try:
        exps = await get(c, sem, f"{API}/v2/expired-instruments/expiries", instrument_key=key) or []
        stats["expiredApi"] = True
        for e in sorted(exps):
            if START.isoformat() <= e < TODAY.isoformat() and e not in out:
                xs = await get(c, sem, f"{API}/v2/expired-instruments/option/contract", instrument_key=key, expiry_date=e)
                out[e] = [{**x, "_expired": True} for x in xs or []]
    except Exception as e:  # noqa: BLE001
        stats["expiredApi"] = False
        stats["errors"].append(f"{code} expired-instruments API: {e}")
    return out


def _first_day(f: Path) -> str | None:
    with open(f) as fh:
        fh.readline()
        line = fh.readline()
    return line[:10] if line else None


async def contract(c, sem, code, e, x, lo, hi):
    f = OUT / "expired" / code / e / f"{int(float(x['strike_price']))}{x['instrument_type']}.csv"
    frm = max(START, date.fromisoformat(e) - timedelta(days=SERIES_WINDOW[code]))
    if f.exists():
        first = _first_day(f)
        if first is None or first <= (frm + timedelta(days=4)).isoformat():
            return  # already covers the window (or the contract simply did not trade earlier)
    k = quote(x["instrument_key"], safe="")
    to = min(TODAY, date.fromisoformat(e))
    try:
        if x["_expired"]:
            d = await get(c, sem, f"{API}/v2/expired-instruments/historical-candle/{k}/1minute/{to}/{frm}")
            rows = (d or {}).get("candles") or []
        else:
            rows = await candles_v3(c, sem, x["instrument_key"], "minutes", 1, frm, to)
            if to == TODAY:
                try:
                    intr = await get(c, sem, f"{API}/v3/historical-candle/intraday/{k}/minutes/1")
                    have = {r[0] for r in rows}
                    rows += [r for r in (intr or {}).get("candles") or [] if r[0] not in have]
                except Exception:  # noqa: BLE001
                    pass
        write(f, rows)
        stats["contracts"] += 1
    except Exception as ex:  # noqa: BLE001
        stats["errors"].append(f"{code} {e} {x['strike_price']}{x['instrument_type']}: {ex}")


async def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(CONC)
    headers = {"Authorization": f"Bearer {await token()}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=40.0, headers=headers) as c:
        rng = await index_data(c, sem)
        expiries = {}
        for code, (key, step) in CODES.items():
            ser = await series(c, sem, code, key)
            expiries[code] = sorted(ser)
            jobs = []
            for e, xs in sorted(ser.items()):
                # trading days on which e is the current or the next series: up to 21 days before it
                days = [d for d in rng[code] if date.fromisoformat(e) - timedelta(days=SERIES_WINDOW[code]) <= date.fromisoformat(d) <= date.fromisoformat(e)]
                if not days:
                    continue
                lo = min(rng[code][d][0] for d in days) - PAD_STEPS * step
                hi = max(rng[code][d][1] for d in days) + PAD_STEPS * step
                for x in xs:
                    if lo <= float(x["strike_price"]) <= hi:
                        jobs.append(contract(c, sem, code, e, x, lo, hi))
            print(f"{code}: {len(ser)} series, downloading {len(jobs)} contracts ...", flush=True)
            await asyncio.gather(*jobs)
            print(f"{code}: done ({stats['contracts']} files so far, {len(stats['errors'])} errors)", flush=True)
    (OUT / "expiries.json").write_text(json.dumps(expiries, indent=1))
    stats["seconds"] = round(time.time() - t0)
    stats["finishedAt"] = datetime.now().isoformat()
    (OUT / "status.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps({k: (v if k != "errors" else v[:15]) for k, v in stats.items()}, indent=1))


asyncio.run(main())
