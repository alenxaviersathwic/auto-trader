#!/usr/bin/env python3
"""
REAL Upstox data for a multi-month replay (default: 4 May 2026 -> today), in two phases so only the option contracts
a trade actually needs are downloaded (a blanket download of every strike would take hours at Upstox's rate limits).

  phase "base"     index 1-min (NIFTY, BANKNIFTY, SENSEX), India VIX 1-min + daily, near-month futures DAILY candles
                   with OI (expired months via Upstox Plus), 1-min of the 10 index heavyweights, daily index candles,
                   and every option series' contract list (strike -> instrument key) for the period
  phase "options"  1-min candles for the contracts listed in logs/realdata6m/needed_contracts.json, which
                   scripts/backtest_range_real.py writes after a first model-priced pass

Run INSIDE the backend container (reuses the Upstox login in the DB); files land in the shared logs/ folder:
    docker exec -i autotrader_backend python - base    < backend-service/scripts/fetch_range_real.py
    docker exec -i autotrader_backend python - options < backend-service/scripts/fetch_range_real.py
Re-running skips files that already exist.
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
OUT = Path(os.environ.get("REALDATA_DIR", "/app/logs/realdata6m"))
API = "https://api.upstox.com"
FROM = date.fromisoformat(os.environ.get("FROM_DATE", "2026-05-04"))
TODAY = date.today()
INDEX = {"NIFTY": "NSE_INDEX|Nifty 50", "BANKNIFTY": "NSE_INDEX|Nifty Bank", "SENSEX": "BSE_INDEX|SENSEX"}
VIX = "NSE_INDEX|India VIX"
# research N3: index heavyweights (NIFTY 5 + bank 5, overlapping)
HEAVY = {"HDFCBANK": "NSE_EQ|INE040A01034", "ICICIBANK": "NSE_EQ|INE090A01021", "RELIANCE": "NSE_EQ|INE002A01018",
         "INFY": "NSE_EQ|INE009A01021", "BHARTIARTL": "NSE_EQ|INE397D01024", "SBIN": "NSE_EQ|INE062A01020",
         "AXISBANK": "NSE_EQ|INE238A01034", "KOTAKBANK": "NSE_EQ|INE237A01028"}
CONC = 4
stats = {"requests": 0, "errors": [], "files": 0}


async def token() -> str:
    if os.environ.get("UPSTOX_ACCESS_TOKEN"):
        return os.environ["UPSTOX_ACCESS_TOKEN"]
    from app.core.db.session import async_session_factory
    from app.modules.opportunities.provider.upstox_market_data import market_data

    async with async_session_factory() as s:
        return await market_data._token(s)


async def get(c, sem, url, **params):
    async with sem:
        for attempt in range(6):
            r = await c.get(url, params=params or None)
            stats["requests"] += 1
            if r.status_code == 429:
                await asyncio.sleep(2.0 * (attempt + 1))
                continue
            await asyncio.sleep(0.15)
            if r.status_code != 200:
                raise RuntimeError(f"{r.status_code} {url.split('?')[0][-80:]}: {r.text[:150]}")
            return (r.json() or {}).get("data")
        raise RuntimeError(f"429 rate-limited: {url[-80:]}")


def write(f: Path, rows) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "open", "high", "low", "close", "volume", "oi"])
        w.writerows(sorted({tuple(r[:7]) for r in rows}))
    stats["files"] += 1


def months(a: date, b: date):
    cur = a
    while cur <= b:
        nxt = min(b, cur + timedelta(days=28))
        yield cur, nxt
        cur = nxt + timedelta(days=1)


async def v3(c, sem, key, unit, n, frm, to):
    d = await get(c, sem, f"{API}/v3/historical-candle/{quote(key, safe='')}/{unit}/{n}/{to}/{frm}")
    return (d or {}).get("candles") or []


async def minutes_range(c, sem, key, frm, to):
    rows = []
    for a, b in months(frm, to):
        try:
            rows += await v3(c, sem, key, "minutes", 1, a, b)
        except Exception as e:  # noqa: BLE001
            stats["errors"].append(f"{key} {a}..{b}: {e}")
    if to >= TODAY:
        try:
            d = await get(c, sem, f"{API}/v3/historical-candle/intraday/{quote(key, safe='')}/minutes/1")
            rows += (d or {}).get("candles") or []
        except Exception:  # noqa: BLE001
            pass
    return rows


async def base(c, sem):
    for name, key in {**INDEX, "INDIAVIX": VIX, **HEAVY}.items():
        f = OUT / "minute" / f"{name}.csv"
        if not f.exists():
            write(f, await minutes_range(c, sem, key, FROM, TODAY))
            print(f"{name}: 1-min saved", flush=True)
    for name, key in {**INDEX, "INDIAVIX": VIX}.items():
        f = OUT / "daily" / f"{name}.csv"
        if not f.exists():
            write(f, await v3(c, sem, key, "days", 1, FROM - timedelta(days=400), TODAY))
    # near-month futures daily with OI (research N2: daily OI build-up) + option contract lists
    contracts: dict[str, dict] = {}
    for code, key in INDEX.items():
        fut_rows = []
        try:
            exps = sorted(await get(c, sem, f"{API}/v2/expired-instruments/expiries", instrument_key=key) or [])
        except Exception as e:  # noqa: BLE001
            exps = []
            stats["errors"].append(f"{code} expiries: {e}")
        exps = [e for e in exps if e >= FROM.isoformat()]
        opt_map: dict[str, dict] = {}
        for e in exps:
            try:
                fx = await get(c, sem, f"{API}/v2/expired-instruments/future/contract", instrument_key=key, expiry_date=e)
                for x in fx or []:
                    d = await get(c, sem, f"{API}/v2/expired-instruments/historical-candle/"
                                          f"{quote(x['instrument_key'], safe='')}/day/{e}/{date.fromisoformat(e) - timedelta(days=45)}")
                    fut_rows += [[*r[:7], e] for r in (d or {}).get("candles") or []]
            except Exception as ex:  # noqa: BLE001
                stats["errors"].append(f"{code} future {e}: {ex}")
            try:
                ox = await get(c, sem, f"{API}/v2/expired-instruments/option/contract", instrument_key=key, expiry_date=e)
                opt_map[e] = {f"{int(float(x['strike_price']))}{x['instrument_type']}": [x["instrument_key"], True]
                              for x in ox or []}
            except Exception as ex:  # noqa: BLE001
                stats["errors"].append(f"{code} options {e}: {ex}")
        try:
            live = await get(c, sem, f"{API}/v2/option/contract", instrument_key=key) or []
            for x in live:
                if x["expiry"] <= (TODAY + timedelta(days=45)).isoformat():
                    opt_map.setdefault(x["expiry"], {})[f"{int(float(x['strike_price']))}{x['instrument_type']}"] = \
                        [x["instrument_key"], False]
        except Exception as ex:  # noqa: BLE001
            stats["errors"].append(f"{code} live options: {ex}")
        try:  # live (not yet expired) near-month future, daily with OI, from the app's own instrument catalog
            from app.modules.opportunities.provider.instrument_catalog import instrument_catalog

            exch = "BSE" if code == "SENSEX" else "NSE"
            fut = await instrument_catalog.near_future(exch, code, roll_on_expiry_day=False)
            if fut:
                rows = await v3(c, sem, fut.key, "days", 1, FROM - timedelta(days=10), TODAY)
                fut_rows += [[*r[:7], fut.expiry] for r in rows]
        except Exception as ex:  # noqa: BLE001
            stats["errors"].append(f"{code} live future: {ex}")
        f = OUT / "futures_daily" / f"{code}.csv"
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["ts", "open", "high", "low", "close", "volume", "oi", "expiry"])
            w.writerows(sorted(fut_rows))
        contracts[code] = opt_map
        print(f"{code}: {len(opt_map)} option series, {len(fut_rows)} futures daily rows", flush=True)
    (OUT / "contracts.json").write_text(json.dumps(contracts))


async def options(c, sem):
    need = json.loads((OUT / "needed_contracts.json").read_text())
    contracts = json.loads((OUT / "contracts.json").read_text())
    jobs = []

    async def one(code, exp, name, frm, to):
        f = OUT / "expired" / code / exp / f"{name}.csv"
        if f.exists():
            return
        ent = contracts.get(code, {}).get(exp, {}).get(name)
        if not ent:
            stats["errors"].append(f"no instrument key {code} {exp} {name}")
            return
        key, expired = ent
        k = quote(key, safe="")
        try:
            if expired:
                d = await get(c, sem, f"{API}/v2/expired-instruments/historical-candle/{k}/1minute/{to}/{frm}")
                rows = (d or {}).get("candles") or []
            else:
                rows = await minutes_range(c, sem, key, date.fromisoformat(frm), date.fromisoformat(to))
            write(f, rows)
        except Exception as ex:  # noqa: BLE001
            stats["errors"].append(f"{code} {exp} {name}: {ex}")

    for n in need:
        jobs.append(one(n["code"], n["expiry"], n["name"], n["from"], n["to"]))
    print(f"downloading {len(jobs)} option contracts ...", flush=True)
    done = 0
    for i in range(0, len(jobs), 40):
        await asyncio.gather(*jobs[i:i + 40])
        done += len(jobs[i:i + 40])
        print(f"  {done}/{len(jobs)}", flush=True)


async def main(phase):
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(CONC)
    headers = {"Authorization": f"Bearer {await token()}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=60.0, headers=headers) as c:
        await (base(c, sem) if phase == "base" else options(c, sem))
    stats["seconds"] = round(time.time() - t0)
    stats["finishedAt"] = datetime.now().isoformat()
    (OUT / f"status_{phase}.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps({k: (v if k != "errors" else v[:12]) for k, v in stats.items()}, indent=1))


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "base"))
