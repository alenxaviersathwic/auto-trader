"""MOMO menus must reach the 0.60-0.80 delta strikes and accept 1 lot at the touch (18 Nov 2026: NIFTY PE setups at
10:45 confirmed but every menu came out empty -- the in-band strikes were past the 9 nearest the money or showed
fewer than 3 lots at the ask)."""
import math

from app.modules.opportunity_finder.provider.underlying_config import get_config
from app.modules.opportunity_finder.service import menu_builder as mb

SPOT = 25220.0


def _leg(strike: float, put: bool, qty: float) -> dict:
    itm = (strike - SPOT) if put else (SPOT - strike)
    delta = 1 / (1 + math.exp(-itm / 170))  # 0.5 at the money, ~0.65 at 100 pts ITM, ~0.86 at 300 pts ITM
    intrinsic = max(0.0, itm)
    ltp = round(intrinsic + 140 * math.exp(-abs(itm) / 400), 1)
    return {"key": f"K{int(strike)}{'PE' if put else 'CE'}", "ltp": ltp, "bid": ltp - 0.2, "ask": ltp + 0.2,
            "oi": 500000, "volume": 100000, "delta": -delta if put else delta, "iv": 12.0,
            "bidQty": qty, "askQty": qty}


def _market(qty: float) -> dict:
    strikes = [{"strike": k, "CE": _leg(k, False, qty), "PE": _leg(k, True, qty)}
               for k in (SPOT // 50 * 50 + 50 * i for i in range(-12, 12))]
    return {"spot": SPOT, "lotUnits": 65,
            "chains": [{"expiry": "2099-12-01", "spot": SPOT, "strikes": strikes, "resistance": None, "support": None}]}


def _setup() -> dict:
    return {"name": "WEDGE_BREAKDOWN", "side": "PE", "strength": 5, "entry": SPOT, "stop": SPOT + 40,
            "target": SPOT - 200}


def test_momo_reaches_in_band_strikes_beyond_the_nearest_nine():
    reasons: dict[str, int] = {}
    menu = mb.build_menu(get_config("NIFTY"), _market(65), "BEARISH", 1.0, setups=[_setup()], require_setup=True,
                         reasons=reasons, atr5=22.0, strike_modes={"CE": "ATM", "PE": "MOMO"})
    assert menu, reasons
    assert all(m["side"] == "PE" and 0.6 <= m["delta"] <= 0.8 for m in menu)
    assert any(m["strike"] - SPOT > 200 for m in menu)  # past the old +-200 point window


def test_one_lot_at_the_touch_is_enough():
    menu = mb.build_menu(get_config("NIFTY"), _market(65), "BEARISH", 1.0, setups=[_setup()], require_setup=True,
                         atr5=22.0, strike_modes={"CE": "ATM", "PE": "MOMO"})
    assert menu


def test_less_than_a_lot_at_the_touch_is_dropped():
    reasons: dict[str, int] = {}
    menu = mb.build_menu(get_config("NIFTY"), _market(30), "BEARISH", 1.0, setups=[_setup()], require_setup=True,
                         reasons=reasons, atr5=22.0, strike_modes={"CE": "ATM", "PE": "MOMO"})
    assert not menu and reasons.get("ask depth<1 lots")


def test_conflicting_setup_is_reported():
    reasons: dict[str, int] = {}
    s = {**_setup(), "conflict": "futures show LONG_BUILDUP"}
    menu = mb.build_menu(get_config("NIFTY"), _market(65), "BEARISH", 1.0, setups=[s], require_setup=True,
                         reasons=reasons, atr5=22.0, strike_modes={"CE": "ATM", "PE": "MOMO"})
    assert not menu and reasons.get("setup conflicts with futures buildup") == 1
