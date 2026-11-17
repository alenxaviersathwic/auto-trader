from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exception.app_exceptions import BusinessException, ConflictException, NotFoundException
from app.modules.strategies.service.rule_command_service import RuleCommandService
from app.modules.strategies.service.strategy_command_service import StrategyCommandService


class ProposalExecutor:
    """
    Executes confirmed proposals against StrategyCommandService and RuleCommandService.
    Runs exclusively within the confirm endpoint inside a single database transaction.
    The LLM has NO ability to invoke this executor.
    """

    def __init__(
        self,
        strategy_command_service: Optional[StrategyCommandService] = None,
        rule_command_service: Optional[RuleCommandService] = None,
    ):
        self.strat_commands = strategy_command_service or StrategyCommandService()
        self.rule_commands = rule_command_service or RuleCommandService()

    async def execute(
        self,
        session: AsyncSession,
        kind: str,
        payload: Dict[str, Any],
        target_code: Optional[str],
        mode: Optional[str],
        provenance: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Executes proposal according to kind and confirm mode.
        Returns resultRefs dictionary containing created or updated entity IDs.
        """
        provenance["confirmedAt"] = datetime.now(timezone.utc).isoformat()

        if kind == "NEW_STRATEGY":
            created = await self.strat_commands.create(session, payload, provenance)
            # If mode is ADD_AND_ACTIVATE, transition to ACTIVE
            if mode == "ADD_AND_ACTIVATE":
                await self.strat_commands.set_lifecycle(session, created["code"], "ACTIVE", "Activated upon proposal confirmation")
                created["lifecycleStatus"] = "ACTIVE"
            return created

        elif kind == "UPDATE_STRATEGY":
            if not target_code:
                raise BusinessException(message="targetCode is required for UPDATE_STRATEGY")
            return await self.strat_commands.update(session, target_code, payload, provenance)

        elif kind == "NEW_RULE":
            return await self.rule_commands.create(session, payload, provenance)

        elif kind == "UPDATE_RULE":
            if not target_code:
                raise BusinessException(message="targetCode is required for UPDATE_RULE")
            return await self.rule_commands.update(session, target_code, payload, provenance)

        elif kind == "SET_LIFECYCLE":
            if not target_code:
                raise BusinessException(message="targetCode is required for SET_LIFECYCLE")
            target_status = payload.get("lifecycleStatus") or payload.get("to")
            return await self.strat_commands.set_lifecycle(session, target_code, target_status, payload.get("reason"))

        elif kind == "SET_ENABLED":
            if not target_code:
                raise BusinessException(message="targetCode is required for SET_ENABLED")
            enabled = payload.get("enabled", True)
            if payload.get("targetType") == "RULE":
                return await self.rule_commands.set_enabled(session, target_code, enabled)
            return await self.strat_commands.set_enabled(session, target_code, enabled)

        elif kind == "DELETE_DRAFT":
            if not target_code:
                raise BusinessException(message="targetCode is required for DELETE_DRAFT")
            if payload.get("targetType") == "RULE":
                return await self.rule_commands.delete_draft(session, target_code)
            return await self.strat_commands.delete_draft(session, target_code)

        elif kind == "RUN_ENGINE":
            engine_code = payload.get("engine", "research")
            from app.modules.system.service.engine_registry import engine_registry
            eng = engine_registry.get(engine_code)
            if not eng:
                raise BusinessException(message=f"Engine '{engine_code}' not found")
            return await eng.start(payload.get("params", {}), session)

        elif kind == "CANCEL_RUN":
            engine_code = payload.get("engine", "research")
            from app.modules.system.service.engine_registry import engine_registry
            eng = engine_registry.get(engine_code)
            if not eng:
                raise BusinessException(message=f"Engine '{engine_code}' not found")
            return await eng.cancel(session)

        else:
            raise BusinessException(message=f"Unsupported proposal kind: {kind}")
