"""Setup-specific risk budget (18 Nov 2026): FII_OPEN_DRIVE may risk up to 5% on one lot as the day's first trade;
everything else keeps the 4% one-lot cap and the session loss budget."""
from app.modules.sessions.service import session_sizing as ss


def _cap(capital=100000.0, realized=0.0, committed_risk=0.0):
    class P:  # a LOCKED pick
        capitalRequired, riskAmount = 0.0, committed_risk
    return ss.capital_state(capital, 4.0, realized, [P()] if committed_risk else [])


def test_fii_first_trade_uses_its_budget():
    # ITM premium 590, stop 520 -> Rs 4,550 risk on a 65-unit lot: over the 4% cap and over the Rs 4k loss budget
    assert ss.lots_for(590.0, 520.0, 65, 70, _cap(), strategy="FII_OPEN_DRIVE") == (1, None)
    lots, why = ss.lots_for(590.0, 520.0, 65, 70, _cap(), strategy="WEDGE_BREAKOUT")
    assert lots is None and "loss budget" in why


def test_budget_has_a_ceiling():
    lots, why = ss.lots_for(590.0, 500.0, 65, 70, _cap(), strategy="FII_OPEN_DRIVE")  # Rs 5,850 > 5%
    assert lots is None and "5% FII_OPEN_DRIVE budget" in why


def test_budget_only_as_the_first_trade():
    assert ss.lots_for(590.0, 520.0, 65, 70, _cap(realized=-500.0), strategy="FII_OPEN_DRIVE")[0] is None
    assert ss.lots_for(590.0, 520.0, 65, 70, _cap(committed_risk=1000.0), strategy="FII_OPEN_DRIVE")[0] is None


def test_setting_parse(monkeypatch):
    from app.core.config.settings import settings

    monkeypatch.setattr(settings, "SETUP_RISK_BUDGET", "FII_OPEN_DRIVE:5, WEDGE_BREAKOUT:4.5")
    assert ss.setup_risk_pct("fii_open_drive") == 5.0 and ss.setup_risk_pct("WEDGE_BREAKOUT") == 4.5
    assert ss.setup_risk_pct("NOISE_BREAKOUT") is None and ss.setup_risk_pct(None) is None
    monkeypatch.setattr(settings, "SETUP_RISK_BUDGET", "")
    assert ss.setup_risk_pct("FII_OPEN_DRIVE") is None
