from datetime import datetime
from decimal import Decimal
import hashlib
import json
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exception.app_exceptions import ConflictException, NotFoundException, ValidationException
from app.core.pagination.page_result import PageResult
from app.modules.strategies.entity.strategy_entity import Strategy
from app.modules.strategies.entity.strategy_performance_snapshot_entity import StrategyPerformanceSnapshot
from app.modules.strategies.entity.strategy_version_entity import StrategyVersion
from app.modules.strategies.repository.performance_repository import PerformanceRepository
from app.modules.strategies.repository.strategy_repository import StrategyRepository
from app.modules.strategies.schema.performance_schema import (
    PerformanceSnapshotCreate,
    PerformanceSnapshotFilter,
    PerformanceSnapshotResponse,
)
from app.modules.strategies.schema.strategy_schema import (
    EvaluateStrategyRequest,
    EvaluateStrategyResponse,
    PerformanceSnapshotSummary,
    RequirementsResponse,
    StrategyCreate,
    StrategyDetailResponse,
    StrategyEnabledUpdate,
    StrategyFilter,
    StrategyLifecycleUpdate,
    StrategyResponse,
    StrategyUpdate,
    StrategyVersionFilter,
    StrategyVersionResponse,
    ValidateDefinitionRequest,
    ValidateDefinitionResponse,
)
from app.modules.strategies.service.definition_validator import DefinitionValidator
from app.modules.strategies.service.health_service import HealthService
from app.modules.strategies.service.reliability_calculator import ReliabilityCalculator
from app.modules.strategies.service.requirements_extractor import RequirementsExtractor
from app.modules.strategies.service.rule_evaluator import RuleEvaluator


class StrategyService:
    """Service providing business logic for strategies, versioning, evaluation, and lifecycle."""

    def __init__(
        self,
        strategy_repo: Optional[StrategyRepository] = None,
        perf_repo: Optional[PerformanceRepository] = None,
        validator: Optional[DefinitionValidator] = None,
        evaluator: Optional[RuleEvaluator] = None,
        extractor: Optional[RequirementsExtractor] = None,
        health_service: Optional[HealthService] = None,
        reliability_calc: Optional[ReliabilityCalculator] = None,
    ):
        self.strategy_repo = strategy_repo or StrategyRepository()
        self.perf_repo = perf_repo or PerformanceRepository()
        self.validator = validator or DefinitionValidator()
        self.evaluator = evaluator or RuleEvaluator()
        self.extractor = extractor or RequirementsExtractor()
        self.health_service = health_service or HealthService()
        self.reliability_calc = reliability_calc or ReliabilityCalculator()

    async def search(self, session: AsyncSession, filter_obj: StrategyFilter) -> PageResult[StrategyResponse]:
        page_res = await self.strategy_repo.search(session, filter_obj)
        resp_list = []
        for s in page_res.list:
            latest_snap = None
            if s.performanceSnapshots:
                latest_snap = PerformanceSnapshotSummary.model_validate(s.performanceSnapshots[0])
            r = StrategyResponse.model_validate(s)
            r.suggestable = s.suggestable
            r.effectiveHealth = s.effectiveHealth
            r.latestSnapshot = latest_snap
            resp_list.append(r)

        return PageResult(
            list=resp_list,
            page=page_res.page,
            limit=page_res.limit,
            totalPages=page_res.totalPages,
            totalItems=page_res.totalItems,
        )

    async def get_by_id(self, session: AsyncSession, strategy_id: int) -> StrategyDetailResponse:
        s = await self.strategy_repo.get_by_id(session, strategy_id)
        if not s:
            raise NotFoundException(message=f"Strategy with id {strategy_id} not found")

        current_v = None
        if s.currentVersionId:
            v_obj = await self.strategy_repo.get_version_by_id(session, s.currentVersionId)
            if v_obj:
                current_v = StrategyVersionResponse.model_validate(v_obj)
        elif s.versions:
            current_v = StrategyVersionResponse.model_validate(s.versions[0])

        snapshots_by_src: Dict[str, PerformanceSnapshotSummary] = {}
        for snap in s.performanceSnapshots:
            if snap.source not in snapshots_by_src:
                snapshots_by_src[snap.source] = PerformanceSnapshotSummary.model_validate(snap)

        r = StrategyDetailResponse.model_validate(s)
        r.suggestable = s.suggestable
        r.effectiveHealth = s.effectiveHealth
        r.currentVersion = current_v
        r.snapshotsBySource = snapshots_by_src
        return r

    async def create(self, session: AsyncSession, request: StrategyCreate) -> StrategyDetailResponse:
        existing = await self.strategy_repo.get_by_code(session, request.code)
        if existing:
            raise ConflictException(message=f"Strategy with code '{request.code}' already exists")

        # Validate definition
        val_res = await self.validator.validate(session, request.definition, request.definitionFormat)
        executable = val_res.executable

        raw_def = json.dumps(request.definition, sort_keys=True)
        content_hash = hashlib.sha256(raw_def.encode("utf-8")).hexdigest()

        strat = Strategy(
            code=request.code,
            name=request.name,
            description=request.description,
            category=request.category,
            structure=request.structure,
            bias=request.bias,
            optionSide=request.optionSide,
            markets=request.markets,
            underlyingTypes=request.underlyingTypes,
            exchange=request.exchange,
            tradingModes=request.tradingModes,
            executionModes=request.executionModes,
            timeframe=request.timeframe,
            definitionFormat=request.definitionFormat,
            executable=executable,
            lifecycleStatus="DRAFT",
            health="HEALTHY",
            validationStatus="UNTESTED",
            enabled=True,
            riskProfile=request.riskProfile,
            references=request.references,
            riskNotes=request.riskNotes,
            howItWorks=request.howItWorks,
            tags=request.tags,
            attributes=request.attributes,
            provenance=request.provenance or {"source": "CUSTOM"},
            reviewFlags=[issue.message for issue in val_res.issues if issue.level == "WARNING"],
        )
        saved = await self.strategy_repo.save(session, strat)

        v1 = StrategyVersion(
            strategyId=saved.id,
            versionNo=1,
            schemaVersion=2,
            definition=request.definition,
            contentHash=content_hash,
            changeNote=request.changeNote or "Initial version",
        )
        saved_v = await self.strategy_repo.save_version(session, v1)
        saved.currentVersionId = saved_v.id
        await self.strategy_repo.save(session, saved)

        return await self.get_by_id(session, saved.id)

    async def update(self, session: AsyncSession, strategy_id: int, request: StrategyUpdate) -> StrategyDetailResponse:
        strat = await self.strategy_repo.get_by_id(session, strategy_id)
        if not strat:
            raise NotFoundException(message=f"Strategy with id {strategy_id} not found")

        if request.name is not None:
            strat.name = request.name
        if request.description is not None:
            strat.description = request.description
        if request.category is not None:
            strat.category = request.category
        if request.structure is not None:
            strat.structure = request.structure
        if request.bias is not None:
            strat.bias = request.bias
        if request.optionSide is not None:
            strat.optionSide = request.optionSide
        if request.markets is not None:
            strat.markets = request.markets
        if request.underlyingTypes is not None:
            strat.underlyingTypes = request.underlyingTypes
        if request.exchange is not None:
            strat.exchange = request.exchange
        if request.tradingModes is not None:
            strat.tradingModes = request.tradingModes
        if request.executionModes is not None:
            strat.executionModes = request.executionModes
        if request.timeframe is not None:
            strat.timeframe = request.timeframe
        if request.riskProfile is not None:
            strat.riskProfile = request.riskProfile
        if request.references is not None:
            strat.references = request.references
        if request.riskNotes is not None:
            strat.riskNotes = request.riskNotes
        if request.howItWorks is not None:
            strat.howItWorks = request.howItWorks
        if request.tags is not None:
            strat.tags = request.tags
        if request.attributes is not None:
            strat.attributes = request.attributes

        # If definition is provided and changed, create new version
        if request.definition is not None:
            raw_def = json.dumps(request.definition, sort_keys=True)
            new_hash = hashlib.sha256(raw_def.encode("utf-8")).hexdigest()

            latest_v = strat.versions[0] if strat.versions else None
            if not latest_v or latest_v.contentHash != new_hash:
                val_res = await self.validator.validate(session, request.definition, strat.definitionFormat)
                strat.executable = val_res.executable
                strat.reviewFlags = [issue.message for issue in val_res.issues if issue.level == "WARNING"]

                next_no = (latest_v.versionNo + 1) if latest_v else 1
                new_v = StrategyVersion(
                    strategyId=strat.id,
                    versionNo=next_no,
                    schemaVersion=2,
                    definition=request.definition,
                    contentHash=new_hash,
                    changeNote=request.changeNote or f"Version {next_no} update",
                )
                saved_v = await self.strategy_repo.save_version(session, new_v)
                strat.currentVersionId = saved_v.id

        await self.strategy_repo.save(session, strat)
        return await self.get_by_id(session, strat.id)

    async def delete(self, session: AsyncSession, strategy_id: int) -> None:
        strat = await self.strategy_repo.get_by_id(session, strategy_id)
        if not strat:
            raise NotFoundException(message=f"Strategy with id {strategy_id} not found")
        await self.strategy_repo.soft_delete(session, strat)

    async def clone(self, session: AsyncSession, strategy_id: int) -> StrategyDetailResponse:
        strat = await self.strategy_repo.get_by_id(session, strategy_id)
        if not strat:
            raise NotFoundException(message=f"Strategy with id {strategy_id} not found")

        current_v = strat.versions[0] if strat.versions else None
        clone_code = f"{strat.code}_copy"
        # ensure unique code
        counter = 1
        while await self.strategy_repo.get_by_code(session, clone_code):
            clone_code = f"{strat.code}_copy_{counter}"
            counter += 1

        definition = current_v.definition if current_v else {}

        clone_req = StrategyCreate(
            code=clone_code,
            name=f"{strat.name} (Copy)",
            description=strat.description,
            category=strat.category,
            structure=strat.structure,
            bias=strat.bias,
            optionSide=strat.optionSide,
            markets=strat.markets,
            underlyingTypes=strat.underlyingTypes,
            exchange=strat.exchange,
            tradingModes=strat.tradingModes,
            executionModes=strat.executionModes,
            timeframe=strat.timeframe,
            definitionFormat=strat.definitionFormat,
            definition=definition,
            riskProfile=strat.riskProfile,
            references=strat.references,
            riskNotes=strat.riskNotes,
            howItWorks=strat.howItWorks,
            tags=strat.tags,
            attributes=strat.attributes,
            provenance={"source": "CUSTOM", "clonedFrom": strat.code},
            changeNote=f"Cloned from {strat.code}",
        )
        return await self.create(session, clone_req)

    async def set_enabled(self, session: AsyncSession, strategy_id: int, request: StrategyEnabledUpdate) -> StrategyResponse:
        strat = await self.strategy_repo.get_by_id(session, strategy_id)
        if not strat:
            raise NotFoundException(message=f"Strategy with id {strategy_id} not found")
        strat.enabled = request.enabled
        await self.strategy_repo.save(session, strat)
        r = StrategyResponse.model_validate(strat)
        r.suggestable = strat.suggestable
        r.effectiveHealth = strat.effectiveHealth
        return r

    async def update_lifecycle(
        self,
        session: AsyncSession,
        strategy_id: int,
        request: StrategyLifecycleUpdate,
    ) -> StrategyResponse:
        strat = await self.strategy_repo.get_by_id(session, strategy_id)
        if not strat:
            raise NotFoundException(message=f"Strategy with id {strategy_id} not found")

        curr = strat.lifecycleStatus
        target = request.to

        # Allowed transitions:
        # DRAFT -> IN_REVIEW -> ACTIVE
        # ACTIVE -> SUSPENDED -> ACTIVE
        # any -> ARCHIVED
        valid_transitions = {
            "DRAFT": {"IN_REVIEW", "ARCHIVED"},
            "IN_REVIEW": {"ACTIVE", "DRAFT", "ARCHIVED"},
            "ACTIVE": {"SUSPENDED", "ARCHIVED"},
            "SUSPENDED": {"ACTIVE", "ARCHIVED"},
            "ARCHIVED": {"DRAFT"},
        }

        if target not in valid_transitions.get(curr, set()):
            raise ValidationException(
                message=f"Invalid lifecycle transition from {curr} to {target}. Allowed: {sorted(list(valid_transitions.get(curr, set())))}"
            )

        if target == "ACTIVE" and not strat.executable:
            raise ConflictException(
                message=f"Cannot move strategy '{strat.code}' to ACTIVE because executable is false (missing handler or registry items).",
                error={"code": "NOT_EXECUTABLE", "strategy": strat.code},
            )

        strat.lifecycleStatus = target
        await self.strategy_repo.save(session, strat)
        r = StrategyResponse.model_validate(strat)
        r.suggestable = strat.suggestable
        r.effectiveHealth = strat.effectiveHealth
        return r

    async def list_versions(
        self,
        session: AsyncSession,
        strategy_id: int,
        filter_obj: StrategyVersionFilter,
    ) -> PageResult[StrategyVersionResponse]:
        page_res = await self.strategy_repo.list_versions(session, strategy_id, filter_obj)
        resp_list = [StrategyVersionResponse.model_validate(v) for v in page_res.list]
        return PageResult(
            list=resp_list,
            page=page_res.page,
            limit=page_res.limit,
            totalPages=page_res.totalPages,
            totalItems=page_res.totalItems,
        )

    async def get_version(self, session: AsyncSession, strategy_id: int, version_no: int) -> StrategyVersionResponse:
        v = await self.strategy_repo.get_version_by_no(session, strategy_id, version_no)
        if not v:
            raise NotFoundException(message=f"Version {version_no} for strategy {strategy_id} not found")
        return StrategyVersionResponse.model_validate(v)

    async def activate_version(self, session: AsyncSession, strategy_id: int, version_no: int) -> StrategyResponse:
        v = await self.strategy_repo.get_version_by_no(session, strategy_id, version_no)
        if not v:
            raise NotFoundException(message=f"Version {version_no} for strategy {strategy_id} not found")
        strat = await self.strategy_repo.get_by_id(session, strategy_id)
        if not strat:
            raise NotFoundException(message=f"Strategy with id {strategy_id} not found")

        val_res = await self.validator.validate(session, v.definition, strat.definitionFormat)
        strat.currentVersionId = v.id
        strat.executable = val_res.executable
        strat.reviewFlags = [issue.message for issue in val_res.issues if issue.level == "WARNING"]
        await self.strategy_repo.save(session, strat)
        r = StrategyResponse.model_validate(strat)
        r.suggestable = strat.suggestable
        r.effectiveHealth = strat.effectiveHealth
        return r

    async def get_requirements(self, session: AsyncSession, strategy_id: int, version_no: int) -> RequirementsResponse:
        v = await self.strategy_repo.get_version_by_no(session, strategy_id, version_no)
        if not v:
            raise NotFoundException(message=f"Version {version_no} for strategy {strategy_id} not found")
        reqs = self.extractor.extract(v.definition)
        return RequirementsResponse(
            strategyId=strategy_id,
            versionNo=version_no,
            requirements=reqs,
        )

    async def validate_definition(self, session: AsyncSession, request: ValidateDefinitionRequest) -> ValidateDefinitionResponse:
        return await self.validator.validate(session, request.definition, request.format)

    async def evaluate(self, session: AsyncSession, request: EvaluateStrategyRequest) -> EvaluateStrategyResponse:
        definition = request.definition
        if not definition and request.versionId:
            v = await self.strategy_repo.get_version_by_id(session, request.versionId)
            if v:
                definition = v.definition

        if not definition:
            raise ValidationException(message="Either 'definition' or 'versionId' must be provided for evaluation")

        return self.evaluator.evaluate_strategy(definition, request.context)

    # Performance
    async def add_performance_snapshot(
        self,
        session: AsyncSession,
        strategy_id: int,
        request: PerformanceSnapshotCreate,
    ) -> PerformanceSnapshotResponse:
        strat = await self.strategy_repo.get_by_id(session, strategy_id)
        if not strat:
            raise NotFoundException(message=f"Strategy with id {strategy_id} not found")

        flags = self.reliability_calc.compute_flags(
            total_trades=request.totalTrades,
            win_rate_pct=request.winRatePct,
            net_pnl=request.netPnl,
            profit_factor=request.profitFactor,
            max_drawdown=request.maxDrawdown,
        )

        snap = StrategyPerformanceSnapshot(
            strategyId=strategy_id,
            versionNo=request.versionNo,
            source=request.source,
            domain=request.domain,
            periodFrom=request.periodFrom,
            periodTo=request.periodTo,
            asOf=request.asOf or datetime.now(),
            totalTrades=request.totalTrades,
            winningTrades=request.winningTrades,
            losingTrades=request.losingTrades,
            winRatePct=request.winRatePct,
            netPnl=request.netPnl,
            profitFactor=request.profitFactor,
            maxDrawdown=request.maxDrawdown,
            legacyHealth=request.legacyHealth,
            reliabilityFlags=flags,
        )
        saved = await self.perf_repo.save(session, snap)

        # Trigger health evaluation
        await self.health_service.evaluate_strategy_health(session, strat)

        return PerformanceSnapshotResponse.model_validate(saved)

    async def search_performance(
        self,
        session: AsyncSession,
        strategy_id: int,
        filter_obj: PerformanceSnapshotFilter,
    ) -> PageResult[PerformanceSnapshotResponse]:
        page_res = await self.perf_repo.search(session, strategy_id, filter_obj)
        resp_list = [PerformanceSnapshotResponse.model_validate(s) for s in page_res.list]
        return PageResult(
            list=resp_list,
            page=page_res.page,
            limit=page_res.limit,
            totalPages=page_res.totalPages,
            totalItems=page_res.totalItems,
        )

    # Inter-module interface
    async def list_suggestable_summaries(
        self, session: AsyncSession, market: str, underlying_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Short public summaries (name, bias, optionSide, description) of suggestable strategies."""
        filt = StrategyFilter(
            market=market,
            underlyingType=underlying_type,
            lifecycleStatus="ACTIVE",
            executable=True,
            limit=100,
        )
        page_res = await self.strategy_repo.search(session, filt)
        return [
            {
                "name": s.name,
                "bias": s.bias,
                "optionSide": s.optionSide,
                "description": (s.description or "")[:160],
            }
            for s in page_res.list
            if s.suggestable
        ]

    async def list_suggestable(
        self,
        session: AsyncSession,
        market: str,
        underlying_type: Optional[str] = None,
        bias: Optional[str] = None,
        trading_mode: Optional[str] = None,
        execution_mode: Optional[str] = None,
    ) -> List[StrategyVersionResponse]:
        """Returns all suggestable strategy versions for given parameters."""
        filt = StrategyFilter(
            market=market,
            underlyingType=underlying_type,
            bias=bias,
            tradingMode=trading_mode,
            executionMode=execution_mode,
            lifecycleStatus="ACTIVE",
            executable=True,
            limit=100,
        )
        page_res = await self.strategy_repo.search(session, filt)
        results = []
        for s in page_res.list:
            if s.suggestable:
                current_v = s.versions[0] if s.versions else None
                if current_v:
                    results.append(StrategyVersionResponse.model_validate(current_v))
        return results
