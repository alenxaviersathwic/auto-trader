from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exception.app_exceptions import BusinessException, NotFoundException
from app.modules.strategies.repository.strategy_repository import StrategyRepository
from app.modules.strategies.schema.strategy_schema import StrategyCreate, StrategyLifecycleUpdate, StrategyUpdate
from app.modules.strategies.service.strategy_service import StrategyService


class StrategyCommandService:
    """
    Internal command service for executing validated proposals on strategies.
    Only called by the ProposalExecutor upon human confirmation.
    """

    def __init__(
        self,
        strategy_service: Optional[StrategyService] = None,
        strategy_repo: Optional[StrategyRepository] = None,
    ):
        self.strategy_service = strategy_service or StrategyService()
        self.strategy_repo = strategy_repo or StrategyRepository()

    async def create(
        self,
        session: AsyncSession,
        payload: Dict[str, Any],
        provenance: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Creates a new strategy in DRAFT lifecycle with UNTESTED validation status."""
        request = StrategyCreate(
            code=payload["code"],
            name=payload.get("name") or payload["code"],
            description=payload.get("description"),
            category=payload.get("category", "CUSTOM"),
            structure=payload.get("structure"),
            bias=payload.get("bias"),
            optionSide=payload.get("optionSide"),
            markets=payload.get("markets", []),
            underlyingTypes=payload.get("underlyingTypes", []),
            exchange=payload.get("exchange", "NSE"),
            tradingModes=payload.get("tradingModes", ["INTRADAY"]),
            executionModes=payload.get("executionModes", ["PAPER"]),
            timeframe=payload.get("timeframe", "5m"),
            definitionFormat=payload.get("definitionFormat", "RULE_TREE"),
            definition=payload.get("definition", {}),
            riskProfile=payload.get("riskProfile"),
            references=payload.get("references"),
            riskNotes=payload.get("riskNotes"),
            howItWorks=payload.get("howItWorks"),
            tags=payload.get("tags"),
            attributes=payload.get("attributes"),
            activeDays=payload.get("activeDays") or [],
            dayOverrides=payload.get("dayOverrides") or [],
            provenance=provenance,
            changeNote="Created from Master Chat Proposal",
        )
        created = await self.strategy_service.create(session, request)
        return {"id": created.id, "code": created.code, "lifecycleStatus": created.lifecycleStatus}

    async def update(
        self,
        session: AsyncSession,
        target_code: str,
        payload: Dict[str, Any],
        provenance: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Creates a new version for the target strategy."""
        strat = await self.strategy_repo.get_by_code(session, target_code)
        if not strat:
            raise NotFoundException(message=f"Strategy with code '{target_code}' not found")

        request = StrategyUpdate(
            name=payload.get("name"),
            description=payload.get("description"),
            category=payload.get("category"),
            structure=payload.get("structure"),
            bias=payload.get("bias"),
            optionSide=payload.get("optionSide"),
            markets=payload.get("markets"),
            underlyingTypes=payload.get("underlyingTypes"),
            exchange=payload.get("exchange"),
            tradingModes=payload.get("tradingModes"),
            executionModes=payload.get("executionModes"),
            timeframe=payload.get("timeframe"),
            definition=payload.get("definition"),
            riskProfile=payload.get("riskProfile"),
            tags=payload.get("tags"),
            activeDays=payload.get("activeDays"),
            dayOverrides=payload.get("dayOverrides"),
            changeNote="Updated via Master Chat Proposal",
        )
        updated = await self.strategy_service.update(session, strat.id, request)
        return {"id": updated.id, "code": updated.code, "currentVersionId": updated.currentVersionId}

    async def set_lifecycle(
        self,
        session: AsyncSession,
        code: str,
        lifecycle_status: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        strat = await self.strategy_repo.get_by_code(session, code)
        if not strat:
            raise NotFoundException(message=f"Strategy with code '{code}' not found")

        req = StrategyLifecycleUpdate(to=lifecycle_status, reason=reason)
        res = await self.strategy_service.update_lifecycle(session, strat.id, req)
        return {"id": res.id, "code": res.code, "lifecycleStatus": res.lifecycleStatus}

    async def set_enabled(
        self,
        session: AsyncSession,
        code: str,
        enabled: bool,
    ) -> Dict[str, Any]:
        strat = await self.strategy_repo.get_by_code(session, code)
        if not strat:
            raise NotFoundException(message=f"Strategy with code '{code}' not found")

        strat.enabled = enabled
        await self.strategy_repo.save(session, strat)
        return {"id": strat.id, "code": strat.code, "enabled": strat.enabled}

    async def delete_draft(
        self,
        session: AsyncSession,
        code: str,
    ) -> Dict[str, Any]:
        strat = await self.strategy_repo.get_by_code(session, code)
        if not strat:
            raise NotFoundException(message=f"Strategy with code '{code}' not found")

        if strat.lifecycleStatus != "DRAFT":
            raise BusinessException(message=f"Only DRAFT strategies can be deleted. Current: {strat.lifecycleStatus}")

        await self.strategy_service.delete(session, strat.id)
        return {"id": strat.id, "code": strat.code, "deleted": True}
