from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.strategies.entity.rule_entity import Rule
from app.modules.strategies.repository.rule_repository import RuleRepository
from app.modules.strategies.schema.rule_schema import CheckRulesRequest, CheckRulesResponse, GuardrailCheckResult
from app.modules.strategies.service.rule_evaluator import RuleEvaluator


class GuardrailService:
    """Service evaluating global guardrail rules against market and order contexts."""

    def __init__(
        self,
        rule_repo: Optional[RuleRepository] = None,
        rule_evaluator: Optional[RuleEvaluator] = None,
    ):
        self.rule_repo = rule_repo or RuleRepository()
        self.evaluator = rule_evaluator or RuleEvaluator()

    async def check(
        self,
        session: AsyncSession,
        request: CheckRulesRequest,
    ) -> CheckRulesResponse:
        context = request.context
        guardrails = await self.rule_repo.get_active_guardrails(session)

        results: List[GuardrailCheckResult] = []
        has_block = False
        has_avoid = False

        for rule in guardrails:
            # Check scope match
            if not self._matches_scope(rule.appliesTo, context):
                continue

            is_stale = rule.isStale
            if is_stale and not request.includeStale:
                # Rule 8: Stale guardrails still show but return met: None (unknown)
                results.append(
                    GuardrailCheckResult(
                        ruleCode=rule.code,
                        ruleName=rule.name,
                        action=rule.action,
                        priority=rule.priority,
                        message=f"[STALE] {rule.conditionText}",
                        met=None,
                        whenMet=False,
                        unlessMet=False,
                        requireMet=True,
                    )
                )
                continue

            # Fetch active rule version content
            content = None
            if rule.versions:
                content = rule.versions[0].content
            elif rule.currentVersionId:
                v = await self.rule_repo.get_version_by_id(session, rule.currentVersionId)
                if v:
                    content = v.content

            if not content or not isinstance(content, dict):
                continue

            when_node = content.get("when")
            unless_node = content.get("unless")
            require_node = content.get("require")

            when_met = True if not when_node else self.evaluator.evaluate_condition_node(when_node, context)
            unless_met = False if not unless_node else self.evaluator.evaluate_condition_node(unless_node, context)
            require_met = True if not require_node else self.evaluator.evaluate_condition_node(require_node, context)

            # A guardrail condition triggers when:
            # 1. 'when' is met and 'unless' is not met
            # 2. OR 'require' is not met
            is_met = False
            if require_node and not require_met:
                is_met = True
            elif when_node and when_met and not unless_met:
                is_met = True

            if is_met:
                if rule.action == "BLOCK":
                    has_block = True
                elif rule.action == "AVOID":
                    has_avoid = True

            results.append(
                GuardrailCheckResult(
                    ruleCode=rule.code,
                    ruleName=rule.name,
                    action=rule.action,
                    priority=rule.priority,
                    message=rule.conditionText,
                    met=is_met,
                    whenMet=when_met,
                    unlessMet=unless_met,
                    requireMet=require_met,
                )
            )

        return CheckRulesResponse(
            results=results,
            hasBlock=has_block,
            hasAvoid=has_avoid,
        )

    def _matches_scope(self, scope: Dict[str, Any], context: Dict[str, Any]) -> bool:
        if not scope or not isinstance(scope, dict):
            return True

        # Check markets
        scope_markets = scope.get("markets")
        ctx_market = context.get("market") or context.get("context", {}).get("market")
        if scope_markets and ctx_market:
            if "ALL" not in scope_markets and ctx_market not in scope_markets:
                return False

        # Check optionSides
        scope_sides = scope.get("optionSides") or scope.get("option_types")
        ctx_side = context.get("optionSide") or context.get("context", {}).get("optionSide")
        if scope_sides and ctx_side:
            if "ALL" not in scope_sides and ctx_side not in scope_sides and "BOTH" not in scope_sides:
                return False

        # Check tradingModes
        scope_modes = scope.get("tradingModes")
        ctx_mode = context.get("tradingMode") or context.get("context", {}).get("tradingMode")
        if scope_modes and ctx_mode:
            if "ALL" not in scope_modes and ctx_mode not in scope_modes:
                return False

        # Check executionDomains
        scope_domains = scope.get("executionDomains") or scope.get("execution_domain")
        ctx_domain = context.get("executionDomain") or context.get("executionMode") or context.get("context", {}).get("executionDomain")
        if scope_domains and ctx_domain:
            if isinstance(scope_domains, list) and ctx_domain not in scope_domains and "ALL" not in scope_domains:
                return False
            if isinstance(scope_domains, str) and scope_domains != "ALL" and ctx_domain != scope_domains:
                return False

        return True
