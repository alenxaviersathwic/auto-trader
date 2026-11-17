"""
Session managers as agents. A trading session is run by ONE session manager; each manager

  - hands the session to its opportunity trader (same code as the manager: FIB_GOLDEN_TRADER / FLOW_MOMENTUM_TRADER),
  - picks the best suggestion every loop pass (session_manager.best_suggestion), and
  - owns an AUTOPSY SUB-AGENT (modules/autopsy): every trade its sessions close is autopsied by it, and only its
    sessions are affected by what it learns (paused setups, applied guards, the earlier-breakeven trail).

Plain code, not LLM / LangGraph agents: deterministic, testable, and cheap enough to run on every tick.
Sessions created before 17 Nov 2026 may still name both traders; they read the merged view (manager None).
"""
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.autopsy.service.learning_service import learning_service
from app.modules.trade_history.service.trader_presets import (
    ALL_PRESET_TRADER_CODES,
    assign_trader_for_opportunity,
    manager_name,
    normalize_trader_codes,
)


@dataclass(frozen=True)
class SessionManagerAgent:
    code: str  # = the trader it runs

    @property
    def name(self) -> str:
        return manager_name(self.code)

    # ───────── autopsy sub-agent ─────────
    def learned_view(self) -> dict[str, Any]:
        """What this manager's autopsy sub-agent has learned (paused setups, applied guards, scorecards)."""
        return learning_service.view_for(self.code)

    async def autopsy(self, db: AsyncSession, trade: Any, pick_risks: list[Any] | None,
                      exchange: str | None) -> Any:
        return await learning_service.on_trade_closed(db, trade, pick_risks, exchange, self.code)


MANAGERS: dict[str, SessionManagerAgent] = {c: SessionManagerAgent(c) for c in ALL_PRESET_TRADER_CODES}


def manager_for_session(session: Any) -> SessionManagerAgent | None:
    """The session's manager; None for an old session that still names both traders."""
    codes = normalize_trader_codes(getattr(session, "traders", None))
    return MANAGERS.get(codes[0]) if len(codes) == 1 else None


def learned_view_for_session(session: Any) -> dict[str, Any]:
    m = manager_for_session(session)
    return m.learned_view() if m else learning_service.view()


def manager_for_trade(session: Any, strategy: str | None) -> SessionManagerAgent:
    """Who autopsies a closed trade: the session's manager, or (old two-trader session) the trader that owned it."""
    return manager_for_session(session) or MANAGERS[assign_trader_for_opportunity(strategy)]
