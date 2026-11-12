#!/usr/bin/env python3
"""
Edge report: per-setup statistics over EVERY saved trade, with the trial-count-aware verdicts from
app/modules/backtest/service/edge_stats.py (research gap 3). Reads the per-day CSVs written by
opportunity_pnl_report.py / backtest scripts (columns: strategy, side, underlying, net).

  PYTHONPATH=. python scripts/edge_report.py                       # all backtest_out/*.csv
  PYTHONPATH=. python scripts/edge_report.py --trials 300 backtest_out/opportunity_pnl_2026-11-0*.csv

--trials = how many strategy variants were tried overall (setups x sides x underlyings x strike modes x parameter
tweaks). Be honest: the deflated Sharpe hurdle rises with it, which is the point.
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.modules.backtest.service import edge_stats as es  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--trials", type=int, default=200)
    a = ap.parse_args()
    files = a.files or sorted((ROOT / "backtest_out").glob("*.csv")) + sorted((ROOT / "backtest_out").glob("*.jsonl"))
    by: dict[str, list[float]] = defaultdict(list)
    allp: list[float] = []
    for f in files:
        with open(f, newline="") as fh:
            if f.suffix == ".jsonl":  # paper ledgers: only CLOSE events are trades
                rows = [e for e in (json.loads(x) for x in fh if x.strip()) if e.get("kind") == "CLOSE"]
            else:
                rows = list(csv.DictReader(fh))
            for r in rows:
                if r.get("outcome") == "PENDING":
                    continue
                net = float(r.get("net") or 0)
                by[f"{r.get('strategy') or '?'} {r.get('side') or ''}".strip()].append(net)
                allp.append(net)
    print(f"{len(files)} file(s), {len(allp)} trades, trials assumed = {a.trials}\n")
    hdr = f"{'setup':<28}{'n':>5}{'win%':>7}{'exp Rs':>9}{'95% CI':>22}{'PF':>6}{'DSR':>7}  verdict"
    print(hdr + "\n" + "-" * len(hdr))
    rows = sorted(by.items(), key=lambda kv: -sum(kv[1]))
    for name, p in rows + [("ALL", allp)]:
        s = es.summarize(p)
        dsr = es.deflated_sharpe(p, a.trials)
        kill, why_k = es.kill_verdict(p)
        live, why_l = es.promotion_verdict(p, a.trials)
        verdict = "SUSPEND: " + why_k if kill else ("LIVE-ELIGIBLE" if live else "PAPER ONLY: " + why_l)
        lo, hi = s.get("ci95", (None, None))
        ci = f"[{lo:+,.0f}, {hi:+,.0f}]" if lo is not None else "-"
        pf = f"{s['profitFactor']:.2f}" if s.get("profitFactor") else "-"
        print(f"{name:<28}{s['n']:>5}{s['winRate']:>7.1f}{s['expectancy']:>+9,.0f}{ci:>22}{pf:>6}"
              f"{(f'{dsr:.2f}' if dsr is not None else '-'):>7}  {verdict}")


if __name__ == "__main__":
    main()
