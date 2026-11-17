from app.modules.backtest.service import premium_sim
from app.modules.backtest.service import range_backtest_service as rs
from app.modules.opportunity_finder.provider.underlying_config import get_config


def test_rule_names_are_stable():
    assert rs._rule_of("TREND_5_20: PE against the multi-day trend (5d UP)") == "TREND_5_20"
    assert rs._rule_of("IB_GATE: price inside the 09:15-11:15 range (1-2)") == "IB_GATE"
    assert rs._rule_of("ORB dropped (no evidence of edge after costs)") == "POLICY: setup switched off"
    assert rs._rule_of("FAILED_BREAK_RECLAIM is a mean-reversion read: short-premium placement only") == \
        "POLICY: short-premium only"


def _bars(path):
    return [{"t": f"2026-11-10T{9 + (i + 15) // 60:02d}:{(i + 15) % 60:02d}:00+05:30", "o": p, "h": p + 2, "l": p - 2,
             "c": p, "v": 1, "oi": 0} for i, p in enumerate(path)]


def test_momo_sim_trails_a_trend_and_stops_a_loser():
    cfg = get_config("NIFTY")
    bm = lambda b: int(b["t"][11:13]) * 60 + int(b["t"][14:16])  # noqa: E731
    up = _bars([25000 + i * 2 for i in range(300)])
    r = premium_sim.simulate_momo(cfg, up, 10, "CE", 24970, 40, 7, bm, close_min=15 * 60 + 30)
    assert r and r.netPnl > 0 and r.riskPerLot > 0 and r.premiumPerLot > 0
    down = _bars([25000 - i * 2 for i in range(300)])
    r = premium_sim.simulate_momo(cfg, down, 10, "CE", 24970, 40, 7, bm, close_min=15 * 60 + 30)
    assert r and r.outcome == "STOP" and r.netPnl < 0
    r = premium_sim.simulate_momo(cfg, up, 10, "CE", 24970, 40, 7, bm, exit_by_min=10 * 60 + 30, close_min=15 * 60 + 30)
    assert r and r.outcome in ("TIME_EXIT", "TRAIL") and r.exitMinute <= 10 * 60 + 30


def test_portfolio_applies_session_rules():
    t = lambda d, tm, ex, pnl, risk=1000, prem=20000: {"date": d, "time": tm, "exitTime": ex, "netPnl": pnl,  # noqa: E731
                                                       "riskPerLot": risk, "premiumPerLot": prem, "lotSize": 65}
    rows = [t("2026-11-10", "10:00", "11:00", 500), t("2026-11-10", "10:30", "11:30", 900),
            t("2026-11-10", "12:00", "13:00", -300, risk=5000), t("2026-11-11", "10:00", "10:30", 200, prem=90000)]
    p = rs._portfolio(rows, 50000, 4.0, "RISK")
    assert p["trades"] == 1 and p["netPnl"] == 500
    assert sum(p["skipped"].values()) == 3
    m = rs._portfolio(rows, 50000, 4.0, "MAX_LOTS")  # 50k buys 2 lots of a 20k premium; 90k premium skipped
    assert [x["lots"] for x in m["tradeList"]] == [2, 2] and m["netPnl"] == 2 * 500 - 2 * 300
    assert m["skipped"] == {"another index position already open": 1, "premium above available capital": 1}


def test_portfolio_allows_parallel_positions_on_opposite_sides_only():
    t = lambda tm, ex, side, pnl: {"date": "2026-11-10", "time": tm, "exitTime": ex, "netPnl": pnl, "side": side,  # noqa: E731
                                   "riskPerLot": 1000, "premiumPerLot": 10000, "lotSize": 65}
    rows = [t("10:00", "11:00", "CE", 500), t("10:10", "10:50", "PE", 300), t("10:20", "10:40", "CE", 200)]
    p = rs._portfolio(rows, 50000, 4.0, "RISK")
    assert p["trades"] == 2 and p["skipped"] == {"another index position already open": 1}


def test_session_block_mirrors_the_live_session():
    fib = {"name": "FIB_GOLDEN_POCKET", "side": "CE", "rr": 1.8}
    momo = {"name": "NOISE_BREAKOUT", "side": "CE", "rr": 2.0}
    # the other trader's setup is out of the session's scope (not a rule that "blocked" it)
    assert rs.session_block(fib, "FLOW_MOMENTUM_TRADER", "LOW", "UP") == (False, None)
    assert rs.session_block(momo, "FIB_GOLDEN_TRADER", "LOW", "UP") == (False, None)
    assert rs.session_block(momo, "ALL", "LOW", "UP") == (True, None)
    assert rs.session_block(fib, "FIB_GOLDEN_TRADER", "LOW", "UP") == (True, None)
    # the live risk gate: trend side, reward:risk, setup class
    assert "against the trend" in rs.session_block(momo, "ALL", "LOW", "DOWN")[1]
    assert rs.session_block(momo, "ALL", "HIGH", "DOWN") == (True, None)
    assert "reward:risk" in rs.session_block({**fib, "rr": 1.2}, "FIB_GOLDEN_TRADER", "LOW", "UP")[1]
    assert "not a proven setup" in rs.session_block({"name": "VWAP_PULLBACK", "side": "CE", "rr": 2}, "ALL", "LOW",
                                                     "UP")[1]


def test_fib_sim_follows_the_fib_trader():
    cfg = get_config("NIFTY")
    bm = lambda b: int(b["t"][11:13]) * 60 + int(b["t"][14:16])  # noqa: E731
    close = 15 * 60 + 30
    # entry 25000, stop 24960, swing (1.0) 25060, extensions 25080 / 25100
    up = _bars([25000 + i for i in range(300)])
    r = premium_sim.simulate_fib(cfg, up, 10, "CE", 24960, 25060, 25080, 25100, 7, bm, close_min=close)
    assert r and r.outcome == "TARGET" and r.netPnl > 0 and r.riskPerLot > 0
    down = _bars([25000 - i for i in range(300)])
    r = premium_sim.simulate_fib(cfg, down, 10, "CE", 24960, 25060, 25080, 25100, 7, bm, close_min=close)
    assert r and r.outcome == "STOP" and r.netPnl < 0
    # runs 90% of the way, then falls back: the 50% lock (80% reached) closes it in profit, not at the stop
    path = [25000 + i * 6 for i in range(10)] + [25054 - i * 3 for i in range(100)]
    r = premium_sim.simulate_fib(cfg, _bars([25000] * 10 + path), 10, "CE", 24960, 25060, 25080, 25100, 7, bm,
                                 close_min=close)
    assert r and r.outcome == "LOCKED" and r.netPnl > 0

