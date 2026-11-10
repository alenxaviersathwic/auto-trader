from datetime import date

from app.modules.backtest.service import expiry_calendar, premium_sim


def test_expiry_for_matches_the_known_9_nov_2026_holiday_shift():
    # Tuesday 10 Nov 2026 is Diwali Balipratipada (a trading holiday): NIFTY's weekly contract that
    # would expire that Tuesday instead expires the previous trading day, Monday 9 Nov.
    assert expiry_calendar.expiry_for("NIFTY", date(2026, 11, 9)) == date(2026, 11, 9)
    assert expiry_calendar.expiry_for("NIFTY", date(2026, 11, 6)) == date(2026, 11, 9)


def test_expiry_for_sensex_weekly_thursday():
    assert expiry_calendar.expiry_for("SENSEX", date(2026, 11, 9)) == date(2026, 11, 12)
    assert expiry_calendar.expiry_for("SENSEX", date(2026, 11, 6)) == date(2026, 11, 12)


def test_expiry_for_banknifty_monthly_shifts_off_guru_nanak_jayanti():
    # 24 Nov 2026 (the last Tuesday of the month) is a trading holiday: the monthly contract
    # expires the previous trading day, Monday 23 Nov.
    assert expiry_calendar.expiry_for("BANKNIFTY", date(2026, 11, 9)) == date(2026, 11, 23)
    assert expiry_calendar.expiry_for("BANKNIFTY", date(2026, 11, 6)) == date(2026, 11, 23)


def test_expiry_for_unknown_code_returns_none():
    assert expiry_calendar.expiry_for("CRUDEOIL", date(2026, 11, 9)) is None


def test_bs_call_put_parity_and_delta_bounds():
    price_ce, delta_ce = premium_sim.bs(24500, 24500, 0.05, 0.15, True)
    price_pe, delta_pe = premium_sim.bs(24500, 24500, 0.05, 0.15, False)
    assert price_ce > 0 and price_pe > 0
    assert 0.45 <= delta_ce <= 0.55  # ATM call delta is close to 0.5
    assert 0.45 <= delta_pe <= 0.55  # ATM put |delta| is close to 0.5 too


def test_pick_strike_respects_the_mode_delta_band():
    from app.modules.opportunities.provider.underlying_config import get_config

    cfg = get_config("NIFTY")
    got = premium_sim.pick_strike(cfg, 24500, 1, 600, True, "OTM", 0.15)
    assert got is not None
    strike, premium, delta = got
    lo, hi = premium_sim.mb.DELTA_BANDS["OTM"]
    assert lo <= delta <= hi
    assert strike > 24500  # an OTM call strike is above spot
