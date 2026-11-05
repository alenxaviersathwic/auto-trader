"""Backtest harness: trade simulation rules (fill, stop-before-target, time stop, skips)."""

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "backtest_setups", Path(__file__).resolve().parents[1] / "scripts" / "backtest_setups.py"
)
bt = importlib.util.module_from_spec(_spec)
sys.modules["backtest_setups"] = bt  # dataclasses resolve their module through sys.modules
_spec.loader.exec_module(bt)

DAY = "2026-11-02"


def _bar(minute, o, h, l, c):
    hh, mm = divmod(minute, 60)
    return {"t": f"{DAY}T{hh:02d}:{mm:02d}:00+05:30", "o": o, "h": h, "l": l, "c": c, "v": 1000.0, "oi": 0.0}


def _flat(start_minute, n, px):
    return [_bar(start_minute + i, px, px + 0.5, px - 0.5, px) for i in range(n)]


SETUP = {"name": "ORB", "side": "CE", "strength": 3, "entry": 25000.0, "stop": 24960.0, "target": 25100.0}
CFG = bt.SimCfg(prem_pct=0.5, delta=0.5, slip_pct=0.0, theta_per_hr=0.0, max_hold=30)


def test_target_hit_exits_at_target():
    # premium0 = 125, target 10% = 12.5 premium = 25 underlying points
    bars = _flat(600, 3, 25000.0) + [_bar(603, 25000.0, 25030.0, 24999.0, 25020.0)]
    res, why = bt.sim_trade(bars, 3, SETUP, CFG, "NIFTY")
    assert res and res["outcome"] == "TARGET" and res["grossPct"] == res["tgtPct"] and not why


def test_stop_checked_before_target_in_same_bar():
    # one bar touches both the stop (-8.75 pts) and the target (+25 pts): the stop must win
    bars = _flat(600, 3, 25000.0) + [_bar(603, 25000.0, 25040.0, 24980.0, 25000.0)]
    res, _ = bt.sim_trade(bars, 3, SETUP, CFG, "NIFTY")
    assert res and res["outcome"] == "STOP" and res["grossPct"] < 0


def test_time_stop_closes_flat_trade():
    bars = _flat(600, 60, 25000.0)
    res, _ = bt.sim_trade(bars, 0, SETUP, CFG, "NIFTY")
    assert res and res["outcome"] == "TIME" and res["holdMin"] >= 30


def test_skips_when_price_already_past_plan():
    bars = _flat(600, 3, 25200.0)  # fill is beyond the target
    res, why = bt.sim_trade(bars, 0, SETUP, CFG, "NIFTY")
    assert res is None and "past setup plan" in why


def test_skip_mode_rejects_wide_chart_stop():
    wide = {**SETUP, "stop": 24800.0}  # 200 pts of chart risk = 80% premium
    cfg = bt.SimCfg(**{**CFG.__dict__, "stop_mode": "skip"})
    res, why = bt.sim_trade(_flat(600, 5, 25000.0), 0, wide, cfg, "NIFTY")
    assert res is None and "wider than cap" in why


def test_stats_and_verdict():
    rows = [{"netPct": 8.0, "outcome": "TARGET", "holdMin": 10}] * 20 + [{"netPct": -4.0, "outcome": "STOP", "holdMin": 5}] * 10
    st = bt.stats(rows)
    assert st["n"] == 30 and st["win%"] == 66.7 and st["avgNet%"] == 4.0
    assert bt.verdict({**st, "t": 5.0}) == "KEEP"
    assert bt.verdict({"n": 10, "avgNet%": 5, "t": 9}).startswith("INSUFFICIENT")
