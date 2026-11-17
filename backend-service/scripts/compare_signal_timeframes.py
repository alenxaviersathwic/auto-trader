"""Compare signal timeframes on the real 6-month replay (range_backtest_service._replay_day = the live pipeline).

  PYTHONPATH=. python scripts/compare_signal_timeframes.py . ../logs/realdata6m <variant> <code> <out.json> [days]
  variants: A_5m_old B_5m_situational C_1m_trigger D_1m_pure   (17 Nov 2026 results: setups.py docstring)
"""
import csv, json, sys, time
from collections import defaultdict
sys.path.insert(0, sys.argv[1])
DATA = sys.argv[2]
from app.core.config.settings import settings
from app.modules.backtest.service import range_backtest_service as rb
from app.modules.opportunity_finder.service import setups as su

def old_agreement(a, side, fam):
    want = "UP" if side == "CE" else "DOWN"
    t = a.get("trend15", "FLAT")
    if fam == "TREND" and t != want:
        return f"15-min trend is {t}, needs {want}", ""
    if fam == "RANGE" and t not in (want, "FLAT"):
        return f"15-min trend is {t}, against", ""
    return None, "old"

VARIANTS = {"A_5m_old": ("5m", True), "B_5m_situational": ("5m", False),
            "C_1m_trigger": ("1m_trigger", False), "D_1m_pure": ("1m", False)}

def load(code):
    days = defaultdict(list)
    for r in csv.DictReader(open(f"{DATA}/minute/{code}.csv")):
        days[r["ts"][:10]].append({"t": r["ts"], "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]),
                                   "c": float(r["close"]), "v": float(r["volume"] or 0), "oi": float(r["oi"] or 0)})
    daily = [{"t": r["ts"], "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]), "c": float(r["close"]),
              "v": 0.0, "oi": 0.0} for r in csv.DictReader(open(f"{DATA}/daily/{code}.csv"))]
    return dict(days), daily

def run(variant, code, limit=None):
    mode, old = VARIANTS[variant]
    settings.SIGNAL_TIMEFRAME = mode
    if old:
        su.tf_agreement = old_agreement
    days, daily = load(code)
    vix_days, _ = load("INDIAVIX")
    vix_daily = {r["ts"][:10]: float(r["close"]) for r in csv.DictReader(open(f"{DATA}/daily/INDIAVIX.csv"))}
    ds = sorted(d for d, v in days.items() if len(v) >= 60)
    if limit:
        ds = ds[:limit]
    trades = []
    for i, d in enumerate(ds):
        prev_vix = next((vix_daily[x] for x in sorted(vix_daily, reverse=True) if x < d), None)
        prev_day = ds[i - 1] if i else None
        res = rb._replay_day(code, d, days[d], daily, prev_vix, vix_days.get(d) or [], rb.ALL_MANAGERS, "LOW", "ALL",
                             days.get(prev_day) if prev_day else None)
        trades += [{**t, "date": d} for t in res.get("trades", [])]
    return trades

if __name__ == "__main__":
    variant, code, out = sys.argv[3], sys.argv[4], sys.argv[5]
    limit = int(sys.argv[6]) if len(sys.argv) > 6 else None
    t0 = time.time()
    tr = run(variant, code, limit)
    json.dump({"variant": variant, "code": code, "secs": round(time.time() - t0, 1), "trades": tr}, open(out, "w"), default=str)
    print(variant, code, len(tr), "trades", round(time.time() - t0, 1), "s")
