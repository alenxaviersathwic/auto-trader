"""Time Machine (service/timemachine.py): pool, replays, real-history walk, lean/verdict, gates and horizon."""
import random

from app.modules.opportunities.service import timemachine as tm


def _session(day: str, start: float, drift: float, rnd: random.Random, bars: int = 75, open_hhmm: str = "09:15"):
    h0, m0 = (int(x) for x in open_hhmm.split(":"))
    out, p = [], start
    for i in range(bars):
        mins = h0 * 60 + m0 + 5 * i
        o = p
        c = o * (1 + drift + rnd.gauss(0, 0.0008))
        hi, lo = max(o, c) * (1 + abs(rnd.gauss(0, 0.0004))), min(o, c) * (1 - abs(rnd.gauss(0, 0.0004)))
        out.append({"t": f"{day}T{mins // 60:02d}:{mins % 60:02d}:00+05:30", "o": o, "h": hi, "l": lo, "c": c,
                    "v": 0, "oi": 0})
        p = c
    return out


def _bars(n_days: int, drift: float, seed: int = 3):
    rnd = random.Random(seed)
    bars = []
    for d in range(n_days):
        bars += _session(f"2026-09-{d + 1:02d}", 25000.0, drift, rnd)
    return bars


def test_sessions_and_pool_are_slot_aligned():
    sessions = tm.sessions_from_bars(_bars(3, 0.0), "09:15")
    assert len(sessions) == 3 and sorted(sessions[0][1]) == list(range(75))
    pool = tm.build_pool(sessions)
    assert 0 not in pool and len(pool[1]) == 3 and len(pool[74]) == 3


def test_same_inputs_same_numbers():
    sessions = tm.sessions_from_bars(_bars(30, 0.0), "09:15")
    pool = tm.build_pool(sessions)
    a = tm.simulate(pool, 25000, 24950, 25100, 20, 26, True)
    b = tm.simulate(pool, 25000, 24950, 25100, 20, 26, True)
    assert a == b and a["seed"] == tm.SEED
    assert abs(a["pTarget"] + a["pStop"] + a["pNeither"] - 1) < 1e-3


def test_an_up_drifting_history_favours_calls_and_hurts_puts():
    sessions = tm.sessions_from_bars(_bars(40, 0.0006), "09:15")
    pool = tm.build_pool(sessions)
    ce = tm.evaluate(sessions, pool, 25000, 24950, 25075, True, 20, 32)
    pe = tm.evaluate(sessions, pool, 25000, 25050, 24925, False, 20, 32)
    assert ce and pe
    assert ce["lean"] > tm.STRONG and "toward the target" in ce["verdict"]
    assert pe["lean"] < tm.DROP_LEAN and "toward the stop" in pe["verdict"]
    assert ce["history"]["sessions"] == 40 and ce["history"]["target"] > ce["history"]["stop"]


def test_not_enough_history_gives_no_verdict():
    sessions = tm.sessions_from_bars(_bars(tm.MIN_SESSIONS - 1, 0.0), "09:15")
    assert tm.evaluate(sessions, tm.build_pool(sessions), 25000, 24950, 25100, True, 20, 26) is None


def test_bad_plan_is_refused():
    sessions = tm.sessions_from_bars(_bars(30, 0.0), "09:15")
    pool = tm.build_pool(sessions)
    assert tm.simulate(pool, 25000, 25010, 25100, 20, 26, True) is None  # stop above a long entry
    assert tm.simulate(pool, 25000, 24950, 24990, 20, 26, True) is None  # target below a long entry


def test_lean_uses_the_break_even_of_the_target_r():
    gap, share, even = tm.lean(0.30, 0.50, 2.0)  # 2R needs 33 % of side hits; 30/80 = 37.5 %
    assert round(even, 3) == 0.333 and round(share, 3) == 0.375 and abs(gap - 0.0417) < 1e-3
    mc = {"pTarget": 0.30, "pStop": 0.50, "rAtTarget": 2.0}
    assert tm.verdict(mc).startswith("Close to break-even")
    assert tm.lean(0, 0, 1.0) is None


def test_judged_needs_enough_side_hits():
    assert not tm.judged({"lean": 0.2, "pTarget": 0.05, "pStop": 0.05})
    assert tm.judged({"lean": 0.2, "pTarget": 0.10, "pStop": 0.10})
    assert not tm.judged({"lean": None, "pTarget": 0.5, "pStop": 0.0})


def test_edge_counts_neither_runs_in_units_of_the_stop():
    t = {"pTarget": 0.4, "pStop": 0.3, "pNeither": 0.3, "avgRNeither": 0.2}
    # 0.4*10 - 0.3*5 + 0.3*0.2*5 - 1 = 4 - 1.5 + 0.3 - 1
    assert tm.edge_pct(t, 10, 5, 1) == 1.8


def test_horizon_is_the_validity_window_capped_at_the_close():
    k, last = tm.horizon("09:15", "15:30", "2026-11-09T10:15:00+05:30", 25)
    assert (k, last) == (12, 17)
    k, last = tm.horizon("09:15", "15:30", "2026-11-09T15:15:00+05:30", 25)
    assert (k, last) == (72, 74)
