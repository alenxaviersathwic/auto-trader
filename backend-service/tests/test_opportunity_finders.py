"""Opportunity finders as one model: optionTypes per finder, sessions get the finders of their scope, managers are
scope-free (17 Nov 2026)."""
import pytest

from app.modules.opportunity_finder.schema.opportunity_finder_schema import (
    OpportunityFinderUpdateRequest,
    clean_option_types,
)
from app.modules.opportunity_finder.service.opportunity_finder_service import OpportunityFinderService
from app.modules.sessions.schema.trading_session_schema import TradingSessionCreateRequest
from app.modules.trade_history.service import trader_presets as tp

REQUIRED = {"code", "name", "shortLabel", "badgeColor", "methodology", "entryLogic", "trailLogic", "strategies",
            "optionTypes", "checks", "drivers", "liveOnly", "sortOrder"}


def test_every_finder_has_the_same_shape():
    for p in tp.TRADER_PRESETS:
        assert REQUIRED <= set(p), p["code"]
        assert p["optionTypes"] and set(p["optionTypes"]) <= {"INDEX", "COMMODITY"}


def test_default_markets_index_national_commodity_international():
    assert tp.default_option_types("FLOW_MOMENTUM_TRADER") == ["INDEX"]
    assert tp.default_option_types("FIB_GOLDEN_TRADER") == ["INDEX"]
    assert tp.default_option_types("COMMODITY_DESK_TRADER") == ["COMMODITY"]


def test_option_types_are_cleaned_and_never_empty():
    assert clean_option_types(["commodity", "INDEX", "index"]) == ["INDEX", "COMMODITY"]
    with pytest.raises(ValueError):
        clean_option_types([])
    with pytest.raises(ValueError):
        clean_option_types(["CURRENCY"])
    assert OpportunityFinderUpdateRequest(optionTypes=["COMMODITY", "INDEX"]).optionTypes == ["INDEX", "COMMODITY"]


def test_cache_covers_and_codes_for(monkeypatch):
    svc = OpportunityFinderService()
    assert svc.codes_for("INDEX") == ["FIB_GOLDEN_TRADER", "FLOW_MOMENTUM_TRADER"]
    assert svc.codes_for("COMMODITY") == ["COMMODITY_DESK_TRADER"]

    class Row:
        def __init__(self, code, types, enabled=True):
            self.code, self.optionTypes, self.enabled = code, types, enabled

    svc._remember([Row("FIB_GOLDEN_TRADER", ["INDEX", "COMMODITY"]), Row("FLOW_MOMENTUM_TRADER", ["INDEX"], False)])
    assert svc.covers("FIB_GOLDEN_TRADER", "COMMODITY")
    assert not svc.covers("FLOW_MOMENTUM_TRADER", "INDEX")  # disabled
    assert svc.codes_for("COMMODITY") == ["FIB_GOLDEN_TRADER", "COMMODITY_DESK_TRADER"]


def test_session_manager_is_scope_free_and_desk_is_not_a_manager():
    assert tp.SESSION_MANAGER_CODES == ("FLOW_MOMENTUM_TRADER", "FIB_GOLDEN_TRADER")
    r = TradingSessionCreateRequest(tradeDate="2026-11-17", userId=1, capital=50000, scope="COMMODITY",
                                    commodityItems=["CRUDEOIL"], traders=["FIB_GOLDEN_TRADER"])
    assert r.traders == ["FIB_GOLDEN_TRADER"] and r.finders == []
    old = TradingSessionCreateRequest(tradeDate="2026-11-17", userId=1, capital=50000, scope="COMMODITY",
                                      commodityItems=["CRUDEOIL"], traders=["COMMODITY_DESK_TRADER"])
    assert old.traders == ["FLOW_MOMENTUM_TRADER"]


def test_session_finders_fall_back_to_old_traders():
    assert tp.session_finder_codes([], ["COMMODITY_DESK_TRADER"]) == ["COMMODITY_DESK_TRADER"]
    assert tp.session_finder_codes(["COMMODITY_DESK_TRADER", "FIB_GOLDEN_TRADER"], ["FLOW_MOMENTUM_TRADER"]) == [
        "FIB_GOLDEN_TRADER", "COMMODITY_DESK_TRADER"]
