#!/usr/bin/env python3
"""
Multi-month replay (default 4 May 2026 -> today) on REAL Upstox data from scripts/fetch_range_real.py.

  pass 1 (no option candles yet): runs everything model-priced and writes logs/realdata6m/needed_contracts.json --
          exactly the contracts the trades / iron-fly checks / drift spreads touch
  -> docker exec -i autotrader_backend python - options < backend-service/scripts/fetch_range_real.py
  pass 2: same command again; every trade with candles is re-priced from REAL option prices

Reports the LIVE configuration, each institutional filter on its own (both halves of the period + regime split),
the expiry iron fly (both entry routes) and the post-expiry drift spread.

  PYTHONPATH=. python scripts/backtest_range_real.py [--data ../logs/realdata6m] [--split 2026-08-17]
"""
from __future__ import annotations

import argparse
import csv
import json
import pickle
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_day as bd  # noqa: E402
import backtest_month_real as bm  # noqa: E402
import backtest_setups as bt  # noqa: E402
from app.core.config.settings import settings  # noqa: E402
from app.modules.backtest.service import edge_stats as es  # noqa: E402
from app.modules.opportunities.provider.underlying_config import get_config  # noqa: E402
from app.modules.opportunities.service import event_calendar, expiry_drift as ed, institutional_filters as inst  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CODES = ("NIFTY", "BANKNIFTY", "SENSEX")
LIVE = settings.INSTITUTIONAL_FILTERS
NEED: dict[tuple, list[str]] = {}
_orig_real = bd.real_bars


def _logged_real(code, strike, ce):
    exp = bd._expiry(code)
    key = (code, exp, f"{int(strike)}{'CE' if ce else 'PE'}")
    NEED.setdefault(key, []).append(bd.DAY)
    return _orig_real(code, strike, ce)


class Ctx:
    def __init__(self, data: Path):
        self.data = data
        self.contracts = json.loads((data / "contracts.json").read_text())
        self.vix_min = bm.by_day(bm.load_csv(data / "minute" / "INDIAVIX.csv"))
        vd = bm.load_csv(data / "daily" / "INDIAVIX.csv")
        self.vix_prev = {cur["t"][:10]: prev["c"] for prev, cur in zip(vd, vd[1:])}
        self.vix_hist = [(b["t"][:10], b["c"]) for b in vd]
        self.heavy = {}
        for names in inst.HEAVYWEIGHTS.values():
            for n in names:
                f = data / "minute" / f"{n}.csv"
                if n not in self.heavy and f.exists():
                    self.heavy[n] = bm.by_day(bm.load_csv(f))
        self.trend: dict[tuple[str, str], dict[int, str]] = {}
        self.er: dict[tuple[str, str], float | None] = {}
        for code in CODES:
            closes = [(b["t"][:10], b["c"]) for b in bm.load_csv(data / "daily" / f"{code}.csv")]
            days = sorted({t for t, _ in closes})
            for d in days + [date.today().isoformat()]:
                prior = [c for t, c in closes if t < d]
                self.trend[(code, d)] = {n: ("UP" if prior[-1] > prior[-1 - n] else "DOWN")
                                         for n in (5, 20) if len(prior) > n}
                if len(prior) > 10:
                    path = sum(abs(prior[i] - prior[i - 1]) for i in range(len(prior) - 10, len(prior)))
                    self.er[(code, d)] = round(abs(prior[-1] - prior[-11]) / path, 3) if path else None
        self.buildup: dict[tuple[str, str], str] = {}
        for code in CODES:
            f = data / "futures_daily" / f"{code}.csv"
            if not f.exists():
                continue
            rows = list(csv.DictReader(open(f)))
            by_date: dict[str, list] = defaultdict(list)
            for r in rows:
                by_date[r["ts"][:10]].append(r)
            days = sorted(by_date)
            near = {d: min(by_date[d], key=lambda r: r["expiry"]) for d in days}  # near-month on that day
            for prev, cur in zip(days, days[1:]):
                a, b = near[prev], near[cur]
                if a["expiry"] != b["expiry"]:
                    continue  # roll day: OI change is meaningless
                st = inst.buildup_state(float(b["close"]) - float(a["close"]), float(b["oi"]) - float(a["oi"]))
                nxt = days[days.index(cur) + 1] if days.index(cur) + 1 < len(days) else None
                if nxt and st:
                    self.buildup[(code, nxt)] = st  # yesterday's state is known before today's open

    def extra(self, code, day, minute, cd):
        out = {"trendDays": self.trend.get((code, day), {}), "er10": self.er.get((code, day))}
        vm = self.vix_min.get(day) or []
        prev = self.vix_prev.get(day)
        cur = next((b for b in reversed(vm) if int(b["t"][11:13]) * 60 + int(b["t"][14:16]) <= minute), None)
        if cur and prev:
            out["vix"] = {"changePct": round((cur["c"] - prev) / prev * 100, 2)}
        if (code, day) in self.buildup:
            out["oiBuildupDaily"] = self.buildup[(code, day)]
        bars = {}
        for n in inst.HEAVYWEIGHTS.get(code, ()):
            hb = (self.heavy.get(n) or {}).get(day) or []
            bars[n] = [b for b in hb if int(b["t"][11:13]) * 60 + int(b["t"][14:16]) < minute]
        hw = inst.heavyweight_state(bars)
        if hw:
            out["heavyweights"] = hw
        return out


def _scan_cache(code: str, late: bool) -> Path:
    return Path.home() / f"range_cands_{code}{'_late' if late else ''}.pkl"


def scan_one(ctx: Ctx, code: str, late: bool):
    cache = _scan_cache(code, late)
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    settings.INSTITUTIONAL_FILTERS = "LATE_WINDOW_LAST" if late else ""
    days = {d: v for d, v in bm.by_day(bm.load_csv(ctx.data / "minute" / f"{code}.csv")).items() if len(v) >= 300}
    daily = bm.load_csv(ctx.data / "daily" / f"{code}.csv")
    seed = [b for b in daily if b["t"][:10] < min(days)]
    x = {"days": days, "daily": daily, "cands": bt.scan(code, days, {}, 0, True, seed_daily=seed),
         "exps": sorted(ctx.contracts.get(code, {}))}
    cache.write_bytes(pickle.dumps(x))
    print(f"scanned {code}{' (late window)' if late else ''}: {len(days)} days", flush=True)
    return x


def scan_all(ctx: Ctx, late: bool):
    return {code: scan_one(ctx, code, late) for code in CODES}


def run_momentum(ctx, data, filters):
    settings.INSTITUTIONAL_FILTERS = filters
    bd.EXTRA_A = ctx.extra
    trades = []
    for code, x in data.items():
        by_d = defaultdict(list)
        for cd in x["cands"]:
            by_d[cd["d"]].append(cd)
        for d in sorted(x["days"]):
            cur = next((e for e in x["exps"] if e >= d), None)
            if not cur:
                continue
            nxt = next((e for e in x["exps"] if e > cur), None)
            bd.DAY, bd.EXPIRY = d, {**bd.EXPIRY, code: cur}
            bd.NEXT_EXPIRY = {**bd.NEXT_EXPIRY, code: nxt} if nxt else {k: v for k, v in bd.NEXT_EXPIRY.items() if k != code}
            tr, _ = bd.replay(code, by_d.get(d, []), x["days"][d])
            trades += [{"day": d, "code": code, **t} for t in tr]
    return trades


def run_flies(ctx, data):
    out = []
    for code, x in data.items():
        for d in sorted(x["days"]):
            if d not in x["exps"]:
                continue
            bd.DAY, bd.EXPIRY = d, {**bd.EXPIRY, code: d}
            before = [b for b in x["daily"] if b["t"][:10] < d]
            out.append(bm.iron_fly_day(code, d, x["days"][d], before, ctx.vix_hist))
    return out


def run_drift(ctx, data):
    """N5 on NIFTY expiry days: bull call spread on the next weekly, entry ENTRY_WINDOW_MIN before close."""
    code, x = "NIFTY", data.get("NIFTY")
    out = []
    if not x:
        return out
    days = sorted(x["days"])
    cfg = get_config(code)
    for i, d in enumerate(days[:-1]):
        if d not in x["exps"]:
            continue
        nxt_exp = next((e for e in x["exps"] if e > d), None)
        if not nxt_exp:
            continue
        bars = x["days"][d]
        close_m = bt._mins(cfg.close_today(datetime.fromisoformat(d).replace(tzinfo=bd.IST)))
        m_in = close_m - ed.ENTRY_WINDOW_MIN
        upto = [b for b in bars if int(b["t"][11:13]) * 60 + int(b["t"][14:16]) <= m_in]
        if not upto:
            continue
        spot = upto[-1]["c"]
        vwap = sum((b["h"] + b["l"] + b["c"]) / 3 for b in upto) / len(upto)
        vix_today = next((v for t, v in ctx.vix_hist if t == d), None)
        pct = bd_pct(vix_today, [v for t, v in ctx.vix_hist if t < d][-250:])
        ok, why = ed.eligible(spot, vwap, pct, bool(event_calendar.event_tags(date.fromisoformat(days[i + 1]))))
        if not ok:
            out.append({"day": d, "result": "SKIP", "net": 0.0, "why": "; ".join(why)})
            continue
        bd.DAY, bd.EXPIRY = d, {**bd.EXPIRY, code: nxt_exp}
        quotes = []
        step = cfg.strikeStep
        atm = round(spot / step) * step
        for k in range(-6, 9):
            s = atm + k * step
            rb = bd.real_bars(code, s, True)
            c = (rb or {}).get(m_in)
            px, dl = bd.bs(code, spot, s, m_in, True)
            px = c["c"] if c else px
            h = px * bd.REAL_HALF_SPREAD_PCT / 100
            quotes.append({"strike": s, "delta": dl, "bid": max(0.05, px - h), "ask": px + h, "real": bool(c)})
        sp = ed.pick(quotes, cfg.lotSize, nxt_exp)
        if not sp:
            continue
        real = all(q["real"] for q in quotes if q["strike"] in (sp.buyStrike, sp.sellStrike))
        nd = days[i + 1]
        bd.DAY = nd
        nbars = x["days"][nd]
        ncl = bt._mins(cfg.close_today(datetime.fromisoformat(nd).replace(tzinfo=bd.IST)))
        val, res = sp.debit, "TIME"
        for b in nbars:
            m = int(b["t"][11:13]) * 60 + int(b["t"][14:16])
            if m > ncl - ed.EXIT_BEFORE_CLOSE_MIN:
                break
            lb, sb = bd.real_bars(code, sp.buyStrike, True), bd.real_bars(code, sp.sellStrike, True)
            if real and lb and sb and m in lb and m in sb:
                v = lb[m]["c"] * (1 - bd.REAL_HALF_SPREAD_PCT / 100) - sb[m]["c"] * (1 + bd.REAL_HALF_SPREAD_PCT / 100)
            else:
                v = bd.bs(code, b["c"], sp.buyStrike, m, True)[0] - bd.bs(code, b["c"], sp.sellStrike, m, True)[0]
            val = v
            if v <= sp.debit * (1 - ed.STOP_FRAC):
                res = "STOP"
                break
        out.append({"day": d, "result": res, "net": ed.pnl_rs(sp, val), "real": real,
                    "why": f"{sp.buyStrike:.0f}/{sp.sellStrike:.0f} debit {sp.debit:.1f} -> {val:.1f}"})
    return out


def bd_pct(v, hist):
    return round(sum(1 for h in hist if h <= v) / len(hist) * 100, 1) if v and len(hist) >= 60 else None


def line(name, tr, split):
    real = [t for t in tr if t.get("real")]
    pn = [t["net"] for t in real]
    s = es.summarize(pn) if pn else {"n": 0}
    h1 = sum(t["net"] for t in real if t["day"] < split)
    h2 = sum(t["net"] for t in real if t["day"] >= split)
    fees = sum(t.get("fees", 0) for t in real)
    model = sum(t["net"] for t in tr if not t.get("real"))
    pf = f"{s['profitFactor']:.2f}" if s.get("profitFactor") else "-"
    print(f"{name:<32}{len(tr):>6}{len(real):>5}{s.get('winRate', 0):>6.1f}{s.get('net', 0):>+11,.0f}{fees:>8,.0f}"
          f"{s.get('expectancy', 0):>+7,.0f}{pf:>6}{s.get('maxDrawdown', 0):>8,.0f}{h1:>+10,.0f}{h2:>+10,.0f}{model:>+9,.0f}",
          flush=True)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT.parent / "logs" / "realdata6m")
    ap.add_argument("--split", default="2026-08-17")
    ap.add_argument("--scan", help="only scan (and cache) this underlying, then exit")
    ap.add_argument("--late", action="store_true", help="with --scan: the LATE_WINDOW_LAST detection variant")
    ap.add_argument("--part", default="all", choices=["all", "live", "filters", "other"])
    a = ap.parse_args()
    bd.DATA_DIR = a.data
    bd.real_bars = _logged_real
    ctx = Ctx(a.data)
    if a.scan:
        scan_one(ctx, a.scan, a.late)
        return
    data = scan_all(ctx, False)
    data_late = scan_all(ctx, True) if a.part in ("all", "filters") else None
    hdr = (f"{'variant':<32}{'trades':>6}{'real':>5}{'win%':>6}{'net(real)':>11}{'fees':>8}{'avg':>7}{'PF':>6}"
           f"{'maxDD':>8}{'H1 net':>10}{'H2 net':>10}{'model':>9}")
    print(f"\nperiod halves split at {a.split}\n" + hdr + "\n" + "-" * len(hdr))
    live_tr = run_momentum(ctx, data, LIVE)
    line(f"LIVE ({LIVE or 'no filters'})", live_tr, a.split)
    if a.part in ("all", "filters"):
        line("without any inst. filter", run_momentum(ctx, data, ""), a.split)
        for f in inst.ALL:
            if f in LIVE.split(","):
                continue
            combo = ",".join(x for x in (LIVE, f) if x)
            line(f"LIVE + {f}", run_momentum(ctx, data_late if f == "LATE_WINDOW_LAST" else data, combo), a.split)
        if a.part == "filters":
            return
    flies = run_flies(ctx, data) if a.part != "filters" else []
    drift = run_drift(ctx, data) if a.part != "filters" else []
    print("\nby underlying (LIVE):")
    for c in CODES:
        line(f"  {c}", [t for t in live_tr if t["code"] == c], a.split)
    print("\nby month (LIVE, real-priced):")
    bym = defaultdict(list)
    for t in live_tr:
        if t.get("real"):
            bym[t["day"][:7]].append(t["net"])
    for mth in sorted(bym):
        s = es.summarize(bym[mth])
        print(f"  {mth}: n={s['n']:>3} win {s['winRate']:>5.1f}% net Rs {s['net']:>+10,.0f}")
    print("\nexpiry iron fly:")
    traded = [x for x in flies if x["result"] not in ("SKIP", "NO_DATA")]
    for x in traded:
        print(f"  {x['day']} {x['code']:<9} {x['result']:<11} net Rs {x['net']:+8,.0f}  {x['why']}")
    print(f"  {len(flies)} expiry days, {len(traded)} flies, net Rs {sum(x['net'] for x in traded):+,.0f}, "
          f"{sum(1 for x in flies if x['result'] == 'NO_DATA')} without option data")
    print("\npost-expiry drift spread (NIFTY):")
    dt = [x for x in drift if x["result"] != "SKIP"]
    for x in dt:
        print(f"  {x['day']} {x['result']:<6} {'REAL' if x.get('real') else 'model'} net Rs {x['net']:+7,.0f}  {x['why']}")
    print(f"  {len(dt)} trades, net Rs {sum(x['net'] for x in dt):+,.0f} (real-priced: "
          f"{sum(x['net'] for x in dt if x.get('real')):+,.0f} over {sum(1 for x in dt if x.get('real'))})")
    need = []
    for (code, exp, name), ds in NEED.items():
        need.append({"code": code, "expiry": exp, "name": name, "from": min(ds),
                     "to": min(max(ds), exp) if max(ds) > exp else max(ds)})
    (a.data / "needed_contracts.json").write_text(json.dumps(sorted(need, key=lambda n: (n["code"], n["expiry"]))))
    have = sum(1 for n in need if (a.data / "expired" / n["code"] / n["expiry"] / f"{n['name']}.csv").exists())
    print(f"\noption contracts touched: {len(need)} ({have} already downloaded) -> {a.data / 'needed_contracts.json'}")
    out = ROOT / "backtest_out" / f"range_real_{date.today().isoformat()}.csv"
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["day", "underlying", "time", "strategy", "side", "strike", "priced", "entry", "exit", "outcome", "net"])
        for t in live_tr:
            w.writerow([t["day"], t["code"], t["time"], t["setup"], t["side"], t["strike"], "REAL" if t.get("real") else "MODEL",
                        round(t["p0"], 2), round(t["px"], 2), t["out"], round(t["net"], 2)])
    print(f"CSV: {out}")


if __name__ == "__main__":
    main()
