from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exception.app_exceptions import BusinessException, NotFoundException
from app.modules.strategies.repository.rule_repository import RuleRepository
from app.modules.strategies.schema.rule_schema import RuleCreate, RuleUpdate
from app.modules.strategies.service.rule_service import RuleService


class RuleCommandService:
    """
    Internal command service for executing validated proposals on rules.
    Only called by the ProposalExecutor upon human confirmation.
    """

    def __init__(
        self,
        rule_service: Optional[RuleService] = None,
        rule_repo: Optional[RuleRepository] = None,
    ):
        self.rule_service = rule_service or RuleService()
        self.rule_repo = rule_repo or RuleRepository()

    async def create(
        self,
        session: AsyncSession,
        payload: Dict[str, Any],
        provenance: Dict[str, Any],
    ) -> Dict[str, Any]:
        request = RuleCreate(
            code=payload["code"],
            name=payload.get("name") or payload["code"],
            ruleKind=payload.get("ruleKind", "GUARDRAIL"),
            ruleType=payload.get("ruleType", "SYSTEM"),
            action=payload.get("action", "AVOID"),
            priority=payload.get("priority", 100),
            appliesTo=payload.get("appliesTo", ["ALL"]),
            conditionText=payload.get("conditionText", ""),
            content=payload.get("content") or payload.get("definition") or {},
            evidence=payload.get("evidence"),
            provenance=provenance,
            changeNote="Created from Master Chat Proposal",
        )
        created = await self.rule_service.create(session, request)
        return {"id": created.id, "code": created.code, "enabled": created.enabled}

    async def update(
        self,
        session: AsyncSession,
        target_code: str,
        payload: Dict[str, Any],
        provenance: Dict[str, Any],
    ) -> Dict[str, Any]:
        rule = await self.rule_repo.get_by_code(session, target_code)
        if not rule:
            raise NotFoundException(message=f"Rule with code '{target_code}' not found")

        request = RuleUpdate(
            name=payload.get("name"),
            action=payload.get("action"),
            priority=payload.get("priority"),
            appliesTo=payload.get("appliesTo"),
            conditionText=payload.get("conditionText"),
            content=payload.get("content") or payload.get("definition"),
            changeNote="Updated via Master Chat Proposal",
        )
        updated = await self.rule_service.update(session, rule.id, request)
        return {"id": updated.id, "code": updated.code, "currentVersionId": updated.currentVersionId}

    async def set_enabled(
        self,
        session: AsyncSession,
        code: str,
        enabled: bool,
    ) -> Dict[str, Any]:
        rule = await self.rule_repo.get_by_code(session, code)
        if not rule:
            raise NotFoundException(message=f"Rule with code '{code}' not found")

        rule.enabled = enabled
        await self.rule_repo.save(session, rule)
        return {"id": rule.id, "code": rule.code, "enabled": rule.enabled}

    async def delete_draft(
        self,
        session: AsyncSession,
        code: str,
    ) -> Dict[str, Any]:
        rule = await self.rule_repo.get_by_code(session, code)
        if not rule:
            raise NotFoundException(message=f"Rule with code '{code}' not found")

        await self.rule_service.delete(session, rule.id)
        return {"id": rule.id, "code": rule.code, "deleted": True}
