from datetime import datetime
from zoneinfo import ZoneInfo

from app.modules.opportunities.service import iron_fly as fly

IST = ZoneInfo("Asia/Kolkata")


def _chain(spot=25000.0, iv_pts=60.0):
    rows = []
    for k in range(-8, 9):
        s = spot + 50 * k
        ce = max(0.5, (spot - s) if s < spot else 0) + max(0.5, iv_pts - abs(s - spot) * 0.45)
        pe = max(0.5, (s - spot) if s > spot else 0) + max(0.5, iv_pts - abs(s - spot) * 0.45)
        rows.append({"strike": s, "CE": {"bid": round(ce - 0.1, 2), "ask": round(ce + 0.1, 2), "key": f"CE{s}"},
                     "PE": {"bid": round(pe - 0.1, 2), "ask": round(pe + 0.1, 2), "key": f"PE{s}"}})
    return {"expiry": "2026-11-17", "strikes": rows}


def _a(**kw):
    a = {"dte": 0, "levels": {"gapPct": 0.1}, "vix": {"changePct": -1.0}, "dayType": {"type": "RANGE"},
         "vrpRatio": 1.25, "vixPctile": 50.0}
    a.update(kw)
    return a


def test_eligibility_filters():
    t = datetime(2026, 11, 17, 10, 0, tzinfo=IST)
    assert fly.eligible(_a(), t)[0]
    assert not fly.eligible(_a(dte=1), t)[0]
    assert not fly.eligible(_a(levels={"gapPct": 0.8}), t)[0]
    assert not fly.eligible(_a(vix={"changePct": 2.0}), t)[0]
    assert not fly.eligible(_a(dayBias={"type": "EXPANSION"}), t)[0]
    assert not fly.eligible(_a(), datetime(2026, 11, 17, 9, 20, tzinfo=IST))[0]
    assert not fly.eligible(_a(), t, ["EVENT_RBI_MPC"])[0]
    assert not fly.eligible(_a(vrpRatio=1.02), t)[0] and not fly.eligible(_a(vrpRatio=None), t)[0]
    assert not fly.eligible(_a(vixPctile=95.0), t)[0] and not fly.eligible(_a(vixPctile=None), t)[0]
    assert not fly.eligible(_a(noise={"state": "ABOVE"}), t)[0]


def test_yang_zhang_and_vrp():
    import random

    random.seed(3)
    px, daily = 25000.0, []
    for _ in range(40):
        o = px * (1 + random.gauss(0, 0.003))
        c = o * (1 + random.gauss(0, 0.007))
        daily.append({"o": o, "h": max(o, c) * 1.002, "l": min(o, c) * 0.998, "c": c})
        px = c
    rv = fly.yang_zhang_vol(daily)
    assert 5 < rv < 25
    assert fly.vrp_ratio(rv * 1.2, daily) == round(rv * 1.2 / rv, 3)
    assert fly.yang_zhang_vol(daily[:5]) is None and fly.vrp_ratio(None, daily) is None
    assert fly.percentile(15.0, [10.0 + i * 0.1 for i in range(100)]) == 51.0 and fly.percentile(1, [1.0]) is None


def test_build_sells_at_bid_buys_at_ask_and_defines_risk():
    f, why = fly.build(_chain(), 25010.0, 50.0, 65, "NIFTY", "NSE", gap_pct=0.0)
    assert f and why is None
    assert f.atm == 25000.0 and f.callWing - f.atm == f.atm - f.putWing
    sells = sum(px for act, _s, _k, px, _key in f.legs if act == "SELL")
    buys = sum(px for act, _s, _k, px, _key in f.legs if act == "BUY")
    assert abs(f.credit - (sells - buys)) < 1e-6 and abs(f.maxLoss - ((f.callWing - f.atm) - f.credit)) < 1e-6
    assert f.takeProfitAt < f.credit < f.stopAt and f.costRs > 160  # 8 orders x Rs 20 brokerage at least


def test_gap_up_widens_the_put_wing():
    f, _ = fly.build(_chain(), 25000.0, 50.0, 65, "NIFTY", "NSE", gap_pct=0.3)
    assert f.atm - f.putWing == f.callWing - f.atm + 50


def test_exit_rules_and_pnl():
    f, _ = fly.build(_chain(), 25000.0, 50.0, 65, "NIFTY", "NSE", gap_pct=0.0)
    t = datetime(2026, 11, 17, 11, 0, tzinfo=IST)
    assert fly.check_exit(f, f.takeProfitAt - 0.1, t) == "TAKE_PROFIT"
    assert fly.check_exit(f, f.stopAt + 0.1, t) == "STOP"
    assert fly.check_exit(f, f.credit, datetime(2026, 11, 17, 14, 50, tzinfo=IST)) == "TIME"
    assert fly.check_exit(f, f.credit, t) is None
    assert fly.check_exit(f, f.credit, t, spot_close_5m=f.atm + f.credit + 1) == "BREAKEVEN"
    assert fly.check_exit(f, f.credit, t, spot_close_5m=f.atm + f.credit - 1) is None
    assert fly.pnl_rs(f, f.credit) == -f.costRs  # flat fly: you still pay the charges


def test_rejects_thin_credit():
    c = _chain(iv_pts=5.0)
    f, why = fly.build(c, 25000.0, 50.0, 65, "NIFTY", "NSE")
    assert f is None and why


def test_paper_engine_opens_then_closes_on_live_quotes(monkeypatch, tmp_path):
    import asyncio

    from app.modules.opportunities.service import iron_fly_paper as paper

    monkeypatch.setattr(paper, "LEDGER", tmp_path / "paper.jsonl")
    monkeypatch.setattr(paper, "CODES", ("NIFTY",))
    monkeypatch.setattr(paper, "is_market_open", lambda cfg, now: True)

    class Ctx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(paper, "async_session_factory", lambda: Ctx())
    state = {"iv": 60.0}

    async def fetch(cfg, s):
        c = _chain(iv_pts=state["iv"])
        c["expiry"] = "2026-11-17"
        for r in c["strikes"]:
            r["CE"]["iv"] = r["PE"]["iv"] = 14.0
        return {"spot": 25000.0, "chains": [c], "lotUnits": 65, "vix": {"changePct": -0.5, "value": 14.5},
                "spotBars1m": [{"o": 25010.0, "c": 25005.0}], "daily": daily}

    monkeypatch.setattr(paper.market_data, "fetch", fetch)

    async def vix_hist(s, days=365):
        return [10.0 + i * 0.05 for i in range(200)]  # today's 14.5 sits at the ~45th percentile

    monkeypatch.setattr(paper.market_data, "vix_history", vix_hist)
    # flat realised vol (tiny daily ranges) vs a 14% IV -> VRP ratio well above 1.1
    daily = [{"t": f"2026-10-{d:02d}T00:00:00+05:30", "o": 25000.0, "h": 25040.0, "l": 24960.0, "c": 25000.0 + (d % 2) * 10}
             for d in range(1, 31)] + [{"t": "2026-11-16T00:00:00+05:30", "o": 25000.0, "h": 25040.0, "l": 24960.0,
                                        "c": 25000.0}]
    asyncio.run(paper.tick(datetime(2026, 11, 17, 10, 0, tzinfo=IST)))
    lines = (tmp_path / "paper.jsonl").read_text().splitlines()
    assert '"kind": "OPEN"' in lines[0]
    state["iv"] = 20.0  # premium decayed: the fly is cheap to buy back -> take profit
    notes = asyncio.run(paper.tick(datetime(2026, 11, 17, 11, 0, tzinfo=IST)))
    assert any("PAPER CLOSE TAKE_PROFIT" in n for n in notes)
    asyncio.run(paper.tick(datetime(2026, 11, 17, 11, 1, tzinfo=IST)))  # closed: nothing more today
    assert sum('"kind": "CLOSE"' in x for x in (tmp_path / "paper.jsonl").read_text().splitlines()) == 1


def test_calmer_than_priced_route_opens_the_gate_when_vrp_fails():
    t = datetime(2026, 11, 17, 10, 0, tzinfo=IST)
    base = _a()
    base.update({"vrpRatio": 0.9, "vixPctile": 50.0})
    assert not fly.eligible(base, t)[0]
    assert fly.implied_move_ratio(120.0, [100.0] * 20) == 1.2
    assert fly.eligible({**base, "impliedMoveRatio": 1.2}, t)[0]
    assert not fly.eligible({**base, "impliedMoveRatio": 1.05}, t)[0]
    assert fly.implied_move_ratio(120.0, [100.0] * 5) is None  # too few past expiries


def test_expiry_drift_spread_rules():
    from app.modules.opportunities.service import expiry_drift as ed

    assert ed.eligible(25100, 25000, 50.0, False)[0]
    assert not ed.eligible(24900, 25000, 50.0, False)[0]
    assert not ed.eligible(25100, 25000, 90.0, False)[0]
    q = [{"strike": 24900 + 50 * i, "delta": max(0.05, 0.75 - 0.08 * i), "bid": 200 - 25 * i, "ask": 201 - 25 * i}
         for i in range(8)]
    sp = ed.pick(q, 65, "2026-11-24")
    assert sp and sp.buyStrike < sp.sellStrike and sp.debit > 0
    assert ed.pnl_rs(sp, sp.debit) < 0  # flat spread still pays charges
    assert ed.killed([-1] * 12 + [1] * 8) and not ed.killed([-1] * 11 + [1] * 9)
