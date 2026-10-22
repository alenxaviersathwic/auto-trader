from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exception.app_exceptions import ConflictException, NotFoundException, ValidationException
from app.core.pagination.page_result import PageResult
from app.modules.strategies.entity.rule_entity import Rule
from app.modules.strategies.entity.rule_version_entity import RuleVersion
from app.modules.strategies.repository.rule_repository import RuleRepository
from app.modules.strategies.schema.rule_schema import (
    CheckRulesRequest,
    CheckRulesResponse,
    RuleCreate,
    RuleDetailResponse,
    RuleFilter,
    RuleResponse,
    RuleUpdate,
    RuleVersionFilter,
    RuleVersionResponse,
)
from app.modules.strategies.service.guardrail_service import GuardrailService


class RuleService:
    """Service providing business logic for guardrail and condition block rules."""

    def __init__(
        self,
        rule_repo: Optional[RuleRepository] = None,
        guardrail_service: Optional[GuardrailService] = None,
    ):
        self.rule_repo = rule_repo or RuleRepository()
        self.guardrail_service = guardrail_service or GuardrailService(self.rule_repo)

    async def search(self, session: AsyncSession, filter_obj: RuleFilter) -> PageResult[RuleResponse]:
        page_res = await self.rule_repo.search(session, filter_obj)
        resp_list = []
        for r in page_res.list:
            res_obj = RuleResponse.model_validate(r)
            res_obj.isStale = r.isStale
            resp_list.append(res_obj)

        return PageResult(
            list=resp_list,
            page=page_res.page,
            limit=page_res.limit,
            totalPages=page_res.totalPages,
            totalItems=page_res.totalItems,
        )

    async def get_by_id(self, session: AsyncSession, rule_id: int) -> RuleDetailResponse:
        rule = await self.rule_repo.get_by_id(session, rule_id)
        if not rule:
            raise NotFoundException(message=f"Rule with id {rule_id} not found")

        current_v = None
        if rule.currentVersionId:
            v_obj = await self.rule_repo.get_version_by_id(session, rule.currentVersionId)
            if v_obj:
                current_v = RuleVersionResponse.model_validate(v_obj)
        elif rule.versions:
            current_v = RuleVersionResponse.model_validate(rule.versions[0])

        used_in = await self.rule_repo.get_strategies_using_rule(session, rule_id)

        resp = RuleDetailResponse.model_validate(rule)
        resp.isStale = rule.isStale
        resp.currentVersion = current_v
        resp.usedInStrategies = used_in
        return resp

    async def create(self, session: AsyncSession, request: RuleCreate) -> RuleDetailResponse:
        existing = await self.rule_repo.get_by_code(session, request.code)
        if existing:
            raise ConflictException(message=f"Rule with code '{request.code}' already exists")

        rule = Rule(
            code=request.code,
            name=request.name,
            ruleKind=request.ruleKind,
            ruleType=request.ruleType,
            action=request.action,
            priority=request.priority,
            appliesTo=request.appliesTo,
            conditionText=request.conditionText,
            evidence=request.evidence,
            reviewBy=request.reviewBy,
            executable=True,
            provenance=request.provenance or {"source": "CUSTOM"},
            enabled=True,
        )
        saved = await self.rule_repo.save(session, rule)

        v1 = RuleVersion(
            ruleId=saved.id,
            versionNo=1,
            content=request.content,
            changeNote=request.changeNote or "Initial version",
        )
        saved_v = await self.rule_repo.save_version(session, v1)
        saved.currentVersionId = saved_v.id
        await self.rule_repo.save(session, saved)

        return await self.get_by_id(session, saved.id)

    async def update(self, session: AsyncSession, rule_id: int, request: RuleUpdate) -> RuleDetailResponse:
        rule = await self.rule_repo.get_by_id(session, rule_id)
        if not rule:
            raise NotFoundException(message=f"Rule with id {rule_id} not found")

        if request.name is not None:
            rule.name = request.name
        if request.action is not None:
            rule.action = request.action
        if request.priority is not None:
            rule.priority = request.priority
        if request.appliesTo is not None:
            rule.appliesTo = request.appliesTo
        if request.conditionText is not None:
            rule.conditionText = request.conditionText
        if request.evidence is not None:
            rule.evidence = request.evidence
        if request.reviewBy is not None:
            rule.reviewBy = request.reviewBy
        if request.enabled is not None:
            rule.enabled = request.enabled

        if request.content is not None:
            latest_v = rule.versions[0] if rule.versions else None
            next_no = (latest_v.versionNo + 1) if latest_v else 1
            new_v = RuleVersion(
                ruleId=rule.id,
                versionNo=next_no,
                content=request.content,
                changeNote=request.changeNote or f"Version {next_no} update",
            )
            saved_v = await self.rule_repo.save_version(session, new_v)
            rule.currentVersionId = saved_v.id

        await self.rule_repo.save(session, rule)
        return await self.get_by_id(session, rule.id)

    async def delete(self, session: AsyncSession, rule_id: int) -> None:
        rule = await self.rule_repo.get_by_id(session, rule_id)
        if not rule:
            raise NotFoundException(message=f"Rule with id {rule_id} not found")

        # Check if rule is in use
        usages = await self.rule_repo.get_strategies_using_rule(session, rule_id)
        if usages:
            strategy_names = [u.name for u in usages]
            raise ConflictException(
                message=f"Cannot delete rule '{rule.code}'. It is in use by {len(usages)} strategies: {', '.join(strategy_names)}",
                error={"code": "RULE_IN_USE", "usedIn": [u.strategyId for u in usages]},
            )

        await self.rule_repo.soft_delete(session, rule)

    async def list_versions(
        self,
        session: AsyncSession,
        rule_id: int,
        filter_obj: RuleVersionFilter,
    ) -> PageResult[RuleVersionResponse]:
        page_res = await self.rule_repo.list_versions(session, rule_id, filter_obj)
        resp_list = [RuleVersionResponse.model_validate(v) for v in page_res.list]
        return PageResult(
            list=resp_list,
            page=page_res.page,
            limit=page_res.limit,
            totalPages=page_res.totalPages,
            totalItems=page_res.totalItems,
        )

    async def check_guardrails(self, session: AsyncSession, request: CheckRulesRequest) -> CheckRulesResponse:
        return await self.guardrail_service.check(session, request)
