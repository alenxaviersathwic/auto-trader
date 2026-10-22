from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exception.app_exceptions import NotFoundException, ValidationException
from app.core.pagination.page_result import PageResult
from app.modules.strategies.entity.health_policy_entity import HealthPolicy
from app.modules.strategies.entity.strategy_entity import Strategy
from app.modules.strategies.entity.strategy_health_event_entity import StrategyHealthEvent
from app.modules.strategies.repository.health_repository import HealthRepository
from app.modules.strategies.repository.performance_repository import PerformanceRepository
from app.modules.strategies.repository.strategy_repository import StrategyRepository
from app.modules.strategies.schema.performance_schema import (
    HealthEventFilter,
    HealthEventResponse,
    HealthOverrideRequest,
    HealthPolicyCreate,
    HealthPolicyFilter,
    HealthPolicyResponse,
    HealthPolicyUpdate,
    HealthResponse,
    RecomputeHealthResponse,
)


class HealthService:
    """Evaluates strategy health policies, manages overrides, and tracks health transitions."""

    def __init__(
        self,
        health_repo: Optional[HealthRepository] = None,
        strategy_repo: Optional[StrategyRepository] = None,
        perf_repo: Optional[PerformanceRepository] = None,
    ):
        self.health_repo = health_repo or HealthRepository()
        self.strategy_repo = strategy_repo or StrategyRepository()
        self.perf_repo = perf_repo or PerformanceRepository()

    async def get_strategy_health(self, session: AsyncSession, strategy_id: int) -> HealthResponse:
        strat = await self.strategy_repo.get_by_id(session, strategy_id)
        if not strat:
            raise NotFoundException(message=f"Strategy with id {strategy_id} not found")

        policy = await self._find_matching_policy(session, strat)
        events = await self.health_repo.get_recent_events_for_strategy(session, strategy_id, limit=10)
        events_resp = [HealthEventResponse.model_validate(e) for e in events]

        policy_dict = None
        if policy:
            policy_dict = {
                "code": policy.code,
                "name": policy.name,
                "scope": policy.scope,
                "params": policy.params,
            }

        return HealthResponse(
            strategyId=strat.id,
            health=strat.health,
            effectiveHealth=strat.effectiveHealth,
            healthOverride=strat.healthOverride,
            healthOverrideReason=strat.healthOverrideReason,
            healthOverrideUntil=strat.healthOverrideUntil,
            policyUsed=policy_dict,
            recentEvents=events_resp,
        )

    async def override_health(
        self,
        session: AsyncSession,
        strategy_id: int,
        request: HealthOverrideRequest,
    ) -> HealthResponse:
        strat = await self.strategy_repo.get_by_id(session, strategy_id)
        if not strat:
            raise NotFoundException(message=f"Strategy with id {strategy_id} not found")

        from_health = strat.effectiveHealth
        strat.healthOverride = request.health
        strat.healthOverrideReason = request.reason
        strat.healthOverrideUntil = request.until

        await self.health_repo.save_event(
            session,
            StrategyHealthEvent(
                strategyId=strat.id,
                fromHealth=from_health,
                toHealth=request.health,
                reason=f"Manual Override: {request.reason}",
                triggeredBy="MANUAL",
            ),
        )
        await self.strategy_repo.save(session, strat)
        return await self.get_strategy_health(session, strategy_id)

    async def evaluate_strategy_health(
        self,
        session: AsyncSession,
        strategy: Strategy,
    ) -> Optional[str]:
        """
        Evaluates health for a strategy based on matching health policy and latest eligible snapshot.
        Excludes flagged snapshots and uses PAPER, LIVE, or BACKTEST.
        """
        # Find latest unflagged snapshot
        snapshots = await self.perf_repo.get_latest_by_source(session, strategy.id)
        eligible_snap = None
        for s in snapshots:
            if s.source in ("PAPER", "LIVE", "BACKTEST") and (not s.reliabilityFlags or len(s.reliabilityFlags) == 0):
                eligible_snap = s
                break

        if not eligible_snap:
            return None

        policy = await self._find_matching_policy(session, strategy)
        if not policy:
            return None

        params = policy.params or {}
        min_trades = params.get("minTrades", 30)
        suspend_pf = params.get("suspendIfProfitFactorBelow", 0.8)
        degrade_pf = params.get("degradeIfProfitFactorBelow", 1.0)
        suspend_dd = params.get("suspendIfDrawdownAbove")

        new_health = "HEALTHY"
        pf = float(eligible_snap.profitFactor)
        dd = float(eligible_snap.maxDrawdown)

        if eligible_snap.totalTrades >= min_trades:
            if suspend_pf is not None and pf < float(suspend_pf):
                new_health = "SUSPENDED"
            elif suspend_dd is not None and dd > float(suspend_dd):
                new_health = "SUSPENDED"
            elif degrade_pf is not None and pf < float(degrade_pf):
                new_health = "DEGRADED"

        if new_health != strategy.health:
            from_health = strategy.health
            strategy.health = new_health
            await self.health_repo.save_event(
                session,
                StrategyHealthEvent(
                    strategyId=strategy.id,
                    fromHealth=from_health,
                    toHealth=new_health,
                    reason=f"Policy '{policy.code}' trigger on snapshot #{eligible_snap.id} (PF: {pf}, Trades: {eligible_snap.totalTrades})",
                    snapshotId=eligible_snap.id,
                    triggeredBy="POLICY",
                ),
            )
            await self.strategy_repo.save(session, strategy)

        return new_health

    async def recompute_all(self, session: AsyncSession) -> RecomputeHealthResponse:
        strategies = await self.strategy_repo.list_all_active(session)
        recomputed = 0
        changed = 0
        details = []

        for strat in strategies:
            old_health = strat.health
            res = await self.evaluate_strategy_health(session, strat)
            if res:
                recomputed += 1
                if res != old_health:
                    changed += 1
                    details.append({
                        "strategyId": strat.id,
                        "code": strat.code,
                        "fromHealth": old_health,
                        "toHealth": res,
                    })

        return RecomputeHealthResponse(
            recomputedCount=recomputed,
            changedCount=changed,
            details=details,
        )

    async def _find_matching_policy(self, session: AsyncSession, strategy: Strategy) -> Optional[HealthPolicy]:
        policies = await self.health_repo.list_active_policies(session)
        best_match = None

        for p in policies:
            scope = p.scope
            if isinstance(scope, str) and scope == "ALL":
                if not best_match:
                    best_match = p
            elif isinstance(scope, dict):
                # Specific scope match
                markets = scope.get("markets", [])
                structures = scope.get("structures", [])
                if (strategy.markets and any(m in markets for m in strategy.markets)) or (
                    strategy.structure and strategy.structure in structures
                ):
                    return p  # Most specific match

        return best_match

    # Health Policy CRUD
    async def search_policies(self, session: AsyncSession, filter_obj: HealthPolicyFilter) -> PageResult[HealthPolicyResponse]:
        page_res = await self.health_repo.search_policies(session, filter_obj)
        resp_list = [HealthPolicyResponse.model_validate(p) for p in page_res.list]
        return PageResult(
            list=resp_list,
            page=page_res.page,
            limit=page_res.limit,
            totalPages=page_res.totalPages,
            totalItems=page_res.totalItems,
        )

    async def create_policy(self, session: AsyncSession, request: HealthPolicyCreate) -> HealthPolicyResponse:
        existing = await self.health_repo.get_policy_by_code(session, request.code)
        if existing:
            raise ValidationException(message=f"Health policy '{request.code}' already exists")

        policy = HealthPolicy(
            code=request.code,
            name=request.name,
            scope=request.scope,
            params=request.params,
            enabled=request.enabled,
        )
        saved = await self.health_repo.save_policy(session, policy)
        return HealthPolicyResponse.model_validate(saved)

    async def update_policy(self, session: AsyncSession, policy_id: int, request: HealthPolicyUpdate) -> HealthPolicyResponse:
        policy = await self.health_repo.get_policy_by_id(session, policy_id)
        if not policy:
            raise NotFoundException(message=f"Health policy with id {policy_id} not found")

        if request.name is not None:
            policy.name = request.name
        if request.scope is not None:
            policy.scope = request.scope
        if request.params is not None:
            policy.params = request.params
        if request.enabled is not None:
            policy.enabled = request.enabled

        saved = await self.health_repo.save_policy(session, policy)
        return HealthPolicyResponse.model_validate(saved)

    async def delete_policy(self, session: AsyncSession, policy_id: int) -> None:
        policy = await self.health_repo.get_policy_by_id(session, policy_id)
        if not policy:
            raise NotFoundException(message=f"Health policy with id {policy_id} not found")
        await self.health_repo.soft_delete_policy(session, policy)

    async def search_events(self, session: AsyncSession, filter_obj: HealthEventFilter) -> PageResult[HealthEventResponse]:
        page_res = await self.health_repo.search_events(session, filter_obj)
        resp_list = [HealthEventResponse.model_validate(e) for e in page_res.list]
        return PageResult(
            list=resp_list,
            page=page_res.page,
            limit=page_res.limit,
            totalPages=page_res.totalPages,
            totalItems=page_res.totalItems,
        )
