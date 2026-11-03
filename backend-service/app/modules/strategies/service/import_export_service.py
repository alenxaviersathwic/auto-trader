from datetime import datetime
from decimal import Decimal
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.strategies.entity.import_batch_entity import ImportBatch
from app.modules.strategies.entity.rule_entity import Rule
from app.modules.strategies.entity.rule_version_entity import RuleVersion
from app.modules.strategies.entity.strategy_entity import Strategy
from app.modules.strategies.entity.strategy_performance_snapshot_entity import StrategyPerformanceSnapshot
from app.modules.strategies.entity.strategy_version_entity import StrategyVersion
from app.modules.strategies.repository.import_repository import ImportRepository
from app.modules.strategies.repository.rule_repository import RuleRepository
from app.modules.strategies.repository.strategy_repository import StrategyRepository
from app.modules.strategies.schema.import_schema import ExportRequest, ExportResponse, ImportBatchResponse, ImportRequest
from app.modules.strategies.service.definition_validator import DefinitionValidator
from app.modules.strategies.service.reliability_calculator import ReliabilityCalculator


class ImportExportService:
    """Handles importing legacy algorithm formats, V2 bundles, and exporting strategy bundles."""

    def __init__(
        self,
        strategy_repo: Optional[StrategyRepository] = None,
        rule_repo: Optional[RuleRepository] = None,
        import_repo: Optional[ImportRepository] = None,
        validator: Optional[DefinitionValidator] = None,
        reliability_calc: Optional[ReliabilityCalculator] = None,
    ):
        self.strategy_repo = strategy_repo or StrategyRepository()
        self.rule_repo = rule_repo or RuleRepository()
        self.import_repo = import_repo or ImportRepository()
        self.validator = validator or DefinitionValidator()
        self.reliability_calc = reliability_calc or ReliabilityCalculator()

    async def import_bundle(
        self,
        session: AsyncSession,
        request: ImportRequest,
    ) -> ImportBatchResponse:
        batch = ImportBatch(
            fileName=request.fileName or "import.json",
            sourceFormat=request.sourceFormat,
            mode=request.mode,
            dryRun=request.dryRun,
            totalItems=0,
            createdCount=0,
            updatedCount=0,
            skippedCount=0,
            failedCount=0,
            errors=[],
            warnings=[],
        )

        data = request.items or {}
        strategies_raw = data.get("strategies", [])
        rules_raw = data.get("rules", []) or data.get("ai_trading_rules", [])

        batch.totalItems = len(strategies_raw) + len(rules_raw)
        warnings_list: List[str] = []
        errors_list: List[Dict[str, Any]] = []

        # 1. Process Strategies
        for idx, strat_item in enumerate(strategies_raw):
            try:
                if request.sourceFormat == "LEGACY_ALGO_V1":
                    strat_data, strat_warnings = self._convert_legacy_strategy(strat_item, idx)
                    warnings_list.extend(strat_warnings)
                else:
                    strat_data = strat_item

                await self._save_or_update_strategy(
                    session=session,
                    strat_data=strat_data,
                    mode=request.mode,
                    dry_run=request.dryRun,
                    batch=batch,
                )
            except Exception as e:
                batch.failedCount += 1
                errors_list.append({
                    "index": idx,
                    "code": strat_item.get("code") or strat_item.get("id"),
                    "message": str(e),
                })

        # 2. Process Rules
        if request.sourceFormat == "LEGACY_ALGO_V1":
            merged_rules = self._merge_legacy_rules(rules_raw)
            for idx, r_data in enumerate(merged_rules):
                try:
                    await self._save_or_update_rule(
                        session=session,
                        rule_data=r_data,
                        mode=request.mode,
                        dry_run=request.dryRun,
                        batch=batch,
                    )
                except Exception as e:
                    batch.failedCount += 1
                    errors_list.append({
                        "index": idx,
                        "code": r_data.get("code"),
                        "message": str(e),
                    })
        else:
            for idx, r_data in enumerate(rules_raw):
                try:
                    await self._save_or_update_rule(
                        session=session,
                        rule_data=r_data,
                        mode=request.mode,
                        dry_run=request.dryRun,
                        batch=batch,
                    )
                except Exception as e:
                    batch.failedCount += 1
                    errors_list.append({
                        "index": idx,
                        "code": r_data.get("code"),
                        "message": str(e),
                    })

        batch.errors = errors_list
        batch.warnings = warnings_list

        if not request.dryRun:
            await self.import_repo.save(session, batch)

        return ImportBatchResponse.model_validate(batch)

    async def _save_or_update_strategy(
        self,
        session: AsyncSession,
        strat_data: Dict[str, Any],
        mode: str,
        dry_run: bool,
        batch: ImportBatch,
    ) -> None:
        code = strat_data.get("code")
        existing = await self.strategy_repo.get_by_code(session, code)

        if existing and mode == "SKIP":
            batch.skippedCount += 1
            return

        definition = strat_data.get("definition", {})
        val_res = await self.validator.validate(session, definition, strat_data.get("definitionFormat", "RULE_TREE"))
        executable = val_res.executable

        raw_def_str = json.dumps(definition, sort_keys=True)
        content_hash = hashlib.sha256(raw_def_str.encode("utf-8")).hexdigest()

        if existing:
            batch.updatedCount += 1
            if dry_run:
                return

            existing.name = strat_data.get("name", existing.name)
            existing.description = strat_data.get("description", existing.description)
            existing.category = strat_data.get("category", existing.category)
            existing.structure = strat_data.get("structure", existing.structure)
            existing.bias = strat_data.get("bias", existing.bias)
            existing.optionSide = strat_data.get("optionSide", existing.optionSide)
            existing.markets = strat_data.get("markets", existing.markets)
            existing.underlyingTypes = strat_data.get("underlyingTypes", existing.underlyingTypes)
            existing.tradingModes = strat_data.get("tradingModes", existing.tradingModes)
            existing.executionModes = strat_data.get("executionModes", existing.executionModes)
            existing.executable = executable
            existing.riskProfile = strat_data.get("riskProfile", existing.riskProfile)
            existing.references = strat_data.get("references", existing.references)
            existing.riskNotes = strat_data.get("riskNotes", existing.riskNotes)
            existing.howItWorks = strat_data.get("howItWorks", existing.howItWorks)
            existing.tags = strat_data.get("tags", existing.tags)
            existing.reviewFlags = strat_data.get("reviewFlags", existing.reviewFlags)

            # Check if definition changed
            latest_v = existing.versions[0] if existing.versions else None
            if not latest_v or latest_v.contentHash != content_hash:
                next_v_no = (latest_v.versionNo + 1) if latest_v else 1
                new_v = StrategyVersion(
                    strategyId=existing.id,
                    versionNo=next_v_no,
                    schemaVersion=2,
                    definition=definition,
                    contentHash=content_hash,
                    changeNote=strat_data.get("changeNote", "Updated via import"),
                )
                await self.strategy_repo.save_version(session, new_v)
                existing.currentVersionId = new_v.id

            await self.strategy_repo.save(session, existing)
        else:
            batch.createdCount += 1
            if dry_run:
                return

            strat = Strategy(
                code=code,
                name=strat_data.get("name", code),
                description=strat_data.get("description"),
                category=strat_data.get("category", "OTHER"),
                structure=strat_data.get("structure"),
                bias=strat_data.get("bias"),
                optionSide=strat_data.get("optionSide"),
                markets=strat_data.get("markets", []),
                underlyingTypes=strat_data.get("underlyingTypes", []),
                exchange=strat_data.get("exchange"),
                tradingModes=strat_data.get("tradingModes", []),
                executionModes=strat_data.get("executionModes", ["PAPER"]),
                timeframe=strat_data.get("timeframe"),
                definitionFormat=strat_data.get("definitionFormat", "RULE_TREE"),
                executable=executable,
                lifecycleStatus=strat_data.get("lifecycleStatus", "DRAFT"),
                health=strat_data.get("health", "HEALTHY"),
                validationStatus=strat_data.get("validationStatus", "UNTESTED"),
                enabled=strat_data.get("enabled", True),
                riskProfile=strat_data.get("riskProfile"),
                references=strat_data.get("references"),
                riskNotes=strat_data.get("riskNotes"),
                howItWorks=strat_data.get("howItWorks"),
                tags=strat_data.get("tags"),
                attributes=strat_data.get("attributes"),
                provenance=strat_data.get("provenance"),
                reviewFlags=strat_data.get("reviewFlags"),
            )
            saved_strat = await self.strategy_repo.save(session, strat)

            # Create Version 1
            v1 = StrategyVersion(
                strategyId=saved_strat.id,
                versionNo=1,
                schemaVersion=2,
                definition=definition,
                contentHash=content_hash,
                changeNote="Initial version from import",
            )
            await self.strategy_repo.save_version(session, v1)
            saved_strat.currentVersionId = v1.id

            # Save Performance Snapshots if any
            for snap_data in strat_data.get("performanceSnapshots", []):
                flags = snap_data.get("reliabilityFlags")
                if flags is None:
                    flags = self.reliability_calc.compute_flags(
                        total_trades=snap_data.get("totalTrades", 0),
                        win_rate_pct=Decimal(str(snap_data.get("winRatePct", 0))),
                        net_pnl=Decimal(str(snap_data.get("netPnl", 0))),
                        profit_factor=Decimal(str(snap_data.get("profitFactor", 0))),
                        max_drawdown=Decimal(str(snap_data.get("maxDrawdown", 0))),
                    )
                snap = StrategyPerformanceSnapshot(
                    strategyId=saved_strat.id,
                    versionNo=1,
                    source=snap_data.get("source", "LEGACY_IMPORT"),
                    domain=snap_data.get("domain", "UNKNOWN"),
                    totalTrades=snap_data.get("totalTrades", 0),
                    winningTrades=snap_data.get("winningTrades", 0),
                    losingTrades=snap_data.get("losingTrades", 0),
                    winRatePct=Decimal(str(snap_data.get("winRatePct", 0))),
                    netPnl=Decimal(str(snap_data.get("netPnl", 0))),
                    profitFactor=Decimal(str(snap_data.get("profitFactor", 0))),
                    maxDrawdown=Decimal(str(snap_data.get("maxDrawdown", 0))),
                    legacyHealth=snap_data.get("legacyHealth"),
                    reliabilityFlags=flags,
                )
                session.add(snap)

            await self.strategy_repo.save(session, saved_strat)

    async def _save_or_update_rule(
        self,
        session: AsyncSession,
        rule_data: Dict[str, Any],
        mode: str,
        dry_run: bool,
        batch: ImportBatch,
    ) -> None:
        code = rule_data.get("code")
        existing = await self.rule_repo.get_by_code(session, code)

        if existing and mode == "SKIP":
            batch.skippedCount += 1
            return

        content = rule_data.get("content", {})
        if existing:
            batch.updatedCount += 1
            if dry_run:
                return

            existing.name = rule_data.get("name", existing.name)
            existing.action = rule_data.get("action", existing.action)
            existing.priority = rule_data.get("priority", existing.priority)
            existing.appliesTo = rule_data.get("appliesTo", existing.appliesTo)
            existing.conditionText = rule_data.get("conditionText", existing.conditionText)
            existing.evidence = rule_data.get("evidence", existing.evidence)
            existing.reviewFlags = rule_data.get("reviewFlags", existing.reviewFlags)

            latest_v = existing.versions[0] if existing.versions else None
            next_v_no = (latest_v.versionNo + 1) if latest_v else 1
            new_v = RuleVersion(
                ruleId=existing.id,
                versionNo=next_v_no,
                content=content,
                changeNote="Updated via import",
            )
            await self.rule_repo.save_version(session, new_v)
            existing.currentVersionId = new_v.id
            await self.rule_repo.save(session, existing)
        else:
            batch.createdCount += 1
            if dry_run:
                return

            rule = Rule(
                code=code,
                name=rule_data.get("name", code),
                ruleKind=rule_data.get("ruleKind", "GUARDRAIL"),
                ruleType=rule_data.get("ruleType", "OTHER"),
                action=rule_data.get("action"),
                priority=rule_data.get("priority", "MEDIUM"),
                appliesTo=rule_data.get("appliesTo", {}),
                conditionText=rule_data.get("conditionText", ""),
                evidence=rule_data.get("evidence"),
                executable=rule_data.get("executable", False),
                reviewFlags=rule_data.get("reviewFlags"),
                provenance=rule_data.get("provenance"),
                enabled=rule_data.get("enabled", True),
            )
            saved_rule = await self.rule_repo.save(session, rule)

            v1 = RuleVersion(
                ruleId=saved_rule.id,
                versionNo=1,
                content=content,
                changeNote="Initial version from import",
            )
            await self.rule_repo.save_version(session, v1)
            saved_rule.currentVersionId = v1.id
            await self.rule_repo.save(session, saved_rule)

    def _convert_legacy_strategy(self, legacy: Dict[str, Any], idx: int) -> Tuple[Dict[str, Any], List[str]]:
        warnings: List[str] = []
        code = legacy.get("id") or legacy.get("code") or f"legacy_strategy_{idx}"
        name = legacy.get("name", code)
        desc = legacy.get("description", "")
        review_flags: List[str] = []

        # Check format
        def_type = legacy.get("type", "")
        cases_raw = legacy.get("cases", [])

        format_val = "RULE_TREE"
        structure = None
        bias = None
        option_side = None

        if not cases_raw and (legacy.get("summary") or "breakout" in code or "crudeoil" in code or "vwap" in code):
            format_val = "SUMMARY"
            review_flags.append("NOT_EXECUTABLE_SUMMARY_ONLY")
            definition = {
                "schemaVersion": 2,
                "format": "SUMMARY",
                "summary": legacy.get("summary") or {
                    "entryLabel": code,
                    "indicators": ["PRICE_ACTION"],
                },
                "extras": {},
            }
        elif "orb15" in code or "ema_pullback" in code:
            format_val = "EVALUATOR"
            review_flags.append("RESEARCH_HYPOTHESIS_NOT_VALIDATED")
            review_flags.append("EVALUATOR_HANDLER_REQUIRED")
            definition = {
                "schemaVersion": 2,
                "format": "EVALUATOR",
                "evaluator": "ORB15" if "orb" in code else "EMA_PULLBACK",
                "parameters": legacy.get("parameters", {}),
                "riskPolicy": {"stopMode": "EVALUATOR_OWNED"},
                "extras": {},
            }
        else:
            # Parse Cases
            converted_cases, case_flags = self._convert_legacy_cases(cases_raw)
            review_flags.extend(case_flags)
            definition = {
                "schemaVersion": 2,
                "format": "RULE_TREE",
                "isParallelCases": legacy.get("isParallelCases", False),
                "cases": converted_cases,
                "bounds": legacy.get("bounds") or {
                    "session": {"entryTime": "09:15", "exitTime": "15:14"},
                    "maxTradesPerDay": 10,
                    "expiryHandling": {},
                },
                "riskPolicy": {"stopMode": "STRATEGY_FIXED"},
                "extras": {},
            }

            # Derive structure, bias, optionSide from legs
            structure, bias, option_side, s_warnings = self._derive_from_cases(converted_cases)
            warnings.extend(s_warnings)

        # Map category
        category = self._map_legacy_category(def_type, code)

        # Map lifecycle
        legacy_health = legacy.get("health", "ACTIVE")
        if format_val == "SUMMARY":
            lifecycle_status = "DRAFT"
            health = "DEGRADED"
        elif legacy_health == "SUSPENDED":
            lifecycle_status = "SUSPENDED"
            health = "SUSPENDED"
        elif legacy_health == "DEGRADED":
            lifecycle_status = "ACTIVE"
            health = "DEGRADED"
        else:
            lifecycle_status = "ACTIVE"
            health = "HEALTHY"

        # Check performance stats
        perf_list = []
        if "trades" in legacy or "totalTrades" in legacy:
            t = legacy.get("totalTrades", legacy.get("trades", 0))
            w = legacy.get("winningTrades", legacy.get("wins", 0))
            l = legacy.get("losingTrades", legacy.get("losses", 0))
            pnl = Decimal(str(legacy.get("netPnl", legacy.get("pnl", 0))))
            pf = Decimal(str(legacy.get("profitFactor", 0)))
            dd = Decimal(str(legacy.get("maxDrawdown", legacy.get("drawdown", 0))))
            wr = Decimal(str(legacy.get("winRatePct", legacy.get("winRate", 0))))

            rel_flags = self.reliability_calc.compute_flags(
                total_trades=t,
                win_rate_pct=wr,
                net_pnl=pnl,
                profit_factor=pf,
                max_drawdown=dd,
            )

            perf_list.append({
                "source": "LEGACY_IMPORT",
                "domain": "UNKNOWN",
                "totalTrades": t,
                "winningTrades": w,
                "losingTrades": l,
                "winRatePct": wr,
                "netPnl": pnl,
                "profitFactor": pf,
                "maxDrawdown": dd,
                "legacyHealth": legacy_health,
                "reliabilityFlags": rel_flags,
            })

        strat_dict = {
            "code": code,
            "name": name,
            "description": desc,
            "category": category,
            "structure": structure,
            "bias": bias,
            "optionSide": option_side,
            "markets": legacy.get("markets", ["NIFTY"]),
            "underlyingTypes": legacy.get("underlyingTypes", ["INDEX"]),
            "exchange": legacy.get("exchange", "NSE"),
            "tradingModes": legacy.get("tradingModes", ["INTRADAY"]),
            "executionModes": legacy.get("executionModes", ["PAPER"]),
            "definitionFormat": format_val,
            "lifecycleStatus": lifecycle_status,
            "health": health,
            "validationStatus": "UNTESTED",
            "enabled": True,
            "riskProfile": legacy.get("riskProfile", {}),
            "references": legacy.get("references", []),
            "riskNotes": legacy.get("riskNotes", []),
            "howItWorks": legacy.get("howItWorks", []),
            "tags": legacy.get("tags", []),
            "attributes": legacy.get("attributes", {}),
            "provenance": {
                "source": "LEGACY_IMPORT",
                "legacy": legacy.get("provenance", {}).get("legacy", {}),
            },
            "reviewFlags": list(set(review_flags)),
            "definition": definition,
            "performanceSnapshots": perf_list,
        }
        return strat_dict, warnings

    def _convert_legacy_cases(self, cases: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        res = []
        flags: List[str] = []

        for c in cases:
            case_key = str(c.get("key", "0"))
            entry = c.get("entry", {})
            entry_when = entry.get("when")
            conv_entry_when, w_flags = self._convert_legacy_condition(entry_when)
            flags.extend(w_flags)

            conv_legs = []
            for l in entry.get("legs", []):
                conv_legs.append(self._convert_legacy_leg(l))

            exit_block = c.get("exit")
            conv_exit = None
            if exit_block and isinstance(exit_block, dict):
                exit_when, x_flags = self._convert_legacy_condition(exit_block.get("when"))
                flags.extend(x_flags)
                conv_exit = {"when": exit_when}

            conv_adjs = []
            for a in c.get("adjustments", []):
                adj_when, a_flags = self._convert_legacy_condition(a.get("when"))
                flags.extend(a_flags)
                conv_adjs.append({
                    "key": a.get("key", "A1"),
                    "when": adj_when,
                    "actions": a.get("actions", []),
                    "extras": a.get("extras", {}),
                })

            res.append({
                "key": case_key,
                "entry": {
                    "when": conv_entry_when,
                    "legs": conv_legs,
                },
                "exit": conv_exit,
                "adjustments": conv_adjs,
                "extras": c.get("extras", {}),
            })

        return res, list(set(flags))

    def _convert_legacy_condition(self, node: Any) -> Tuple[Any, List[str]]:
        flags: List[str] = []
        if not node or not isinstance(node, dict):
            return node, flags

        if "op" in node:
            conv_items = []
            for it in node.get("items", []):
                ci, f = self._convert_legacy_condition(it)
                conv_items.append(ci)
                flags.extend(f)
            return {"op": node["op"], "items": conv_items}, flags

        # Leaf condition
        left = self._parse_legacy_operand(node.get("left"))
        right = self._parse_legacy_operand(node.get("right"))
        operator = self._map_legacy_operator(node.get("operator", "EQUALS"))

        if (isinstance(left, dict) and left.get("source") == "TIME") or (
            isinstance(right, dict) and right.get("type") == "TIME"
        ):
            if operator == "EQUALS":
                flags.append("TIME_EQUALS_NEEDS_REACHED_SEMANTICS")

        if isinstance(left, dict) and left.get("source") == "INDICATOR" and left.get("params") is None:
            flags.append("INDICATOR_PARAMS_UNSPECIFIED")
        if isinstance(left, dict) and left.get("source") == "PRICE" and left.get("timeframe") is None:
            flags.append("TIMEFRAME_USES_ENGINE_DEFAULT")

        return {
            "left": left,
            "operator": operator,
            "right": right,
        }, flags

    def _parse_legacy_operand(self, op: Any) -> Any:
        if not op:
            return op
        if isinstance(op, (int, float, bool)):
            return {"const": op}
        if isinstance(op, dict):
            if "const" in op or "source" in op or "param" in op:
                return op
            return op

        if isinstance(op, str):
            # Check if time format (HH:MM:SS or HH:MM)
            if re.match(r"^\d{2}:\d{2}(:\d{2})?$", op):
                return {"const": op, "type": "TIME"}

            # Try numeric
            try:
                if "." in op:
                    return {"const": float(op)}
                return {"const": int(op)}
            except ValueError:
                pass

            s = op.strip()
            # Legacy string operand mappings:
            if s == "timeOfDay":
                return {"source": "TIME", "field": "timeOfDay"}
            if s == "daysToExpire":
                return {"source": "CONTEXT", "field": "daysToExpire"}
            if s.startswith("Current 5 minute."):
                field = s.replace("Current 5 minute.", "")
                return {"source": "PRICE", "field": field, "bar": "CURRENT", "timeframe": "5m"}
            if s.startswith("current."):
                field = s.replace("current.", "")
                return {"source": "PRICE", "field": field, "bar": "CURRENT", "timeframe": None}
            if s.startswith("previous."):
                field = s.replace("previous.", "")
                return {"source": "PRICE", "field": field, "bar": "PREVIOUS", "timeframe": None}
            if s.startswith("yesterday."):
                field = s.replace("yesterday.", "")
                return {"source": "DAY", "day": "YESTERDAY", "field": field}
            if s.startswith("today."):
                field = s.replace("today.", "")
                return {"source": "DAY", "day": "TODAY", "field": field}

            # Indicators
            if s in ("superTrend", "SuperTrend", "SUPERTREND"):
                return {"source": "INDICATOR", "code": "SUPERTREND", "output": "value", "params": None}
            if s in ("relativeStrengthIndex", "rsi", "RSI"):
                return {"source": "INDICATOR", "code": "RSI", "output": "value", "params": None}
            if s in ("commodityChannelIndex", "cci", "CCI"):
                return {"source": "INDICATOR", "code": "CCI", "output": "value", "params": None}
            if s.startswith("adx.") or s == "ADX":
                return {"source": "INDICATOR", "code": "ADX", "output": "adx", "params": None}
            if s in ("vwap.currentDayVWAP", "vwap", "VWAP"):
                return {"source": "INDICATOR", "code": "VWAP", "output": "currentDay", "params": None}
            if s.startswith("pivotPoints.") or s.startswith("PivotPoints."):
                lvl = s.split(".")[-1].upper()
                return {"source": "INDICATOR", "code": "PIVOT_POINTS", "output": lvl, "params": None}
            if "BB." in s or "Bollinger" in s:
                output = "middle"
                if "upper" in s.lower():
                    output = "upper"
                elif "lower" in s.lower():
                    output = "lower"
                return {"source": "INDICATOR", "code": "BBANDS", "output": output, "params": None}
            if "exponentialMovingAverage" in s or "EMA" in s:
                return {"source": "INDICATOR", "code": "EMA", "output": "value", "params": None}

            # Position field check
            m = re.match(r"^case\.(\w+)\.leg\.(\w+)\.(\w+)$", s)
            if m:
                return {
                    "source": "POSITION",
                    "caseKey": m.group(1),
                    "legId": m.group(2),
                    "field": m.group(3),
                }

            return {"const": s}

        return op

    def _map_legacy_operator(self, op: str) -> str:
        mapping = {
            "isAbove": "IS_ABOVE",
            "isBelow": "IS_BELOW",
            "equalTo": "EQUALS",
            "crossesAbove": "CROSSES_ABOVE",
            "crossesBelow": "CROSSES_BELOW",
            "isAboveOrEqual": "IS_ABOVE_OR_EQUAL",
            "isBelowOrEqual": "IS_BELOW_OR_EQUAL",
            "between": "BETWEEN",
            "in": "IN",
            "notIn": "NOT_IN",
        }
        return mapping.get(op, op.upper())

    def _convert_legacy_leg(self, leg: Dict[str, Any]) -> Dict[str, Any]:
        inst = leg.get("instrument", {})
        strike = inst.get("strike", {})
        selector = strike.get("selector", "ATM_OFFSET")
        steps = strike.get("steps", 0)

        return {
            "legId": str(leg.get("legId", "1")),
            "side": leg.get("side", "BUY"),
            "instrument": {
                "kind": inst.get("kind", "OPTION"),
                "optionType": inst.get("optionType", "CE"),
                "expiry": inst.get("expiry", {"cycle": "WEEKLY", "index": 1}),
                "strike": {
                    "selector": selector,
                    "steps": steps,
                    **{k: v for k, v in strike.items() if k not in ("selector", "steps")},
                },
            },
            "quantity": leg.get("quantity", {"unit": "LOT", "value": 1}),
            "stopLoss": leg.get("stopLoss"),
            "target": leg.get("target"),
            "reEntryCount": leg.get("reEntryCount", 0),
            "reExecuteCount": leg.get("reExecuteCount", 0),
            "extras": leg.get("extras", {}),
        }

    def _derive_from_cases(self, cases: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], Optional[str], List[str]]:
        warnings: List[str] = []
        if not cases:
            return None, None, None, warnings

        # Analyze legs across cases
        all_legs = []
        for c in cases:
            all_legs.extend(c.get("entry", {}).get("legs", []))

        if len(all_legs) == 1:
            leg = all_legs[0]
            opt_type = leg.get("instrument", {}).get("optionType", "CE")
            side = leg.get("side", "BUY")
            if side == "BUY":
                if opt_type == "CE":
                    return "SINGLE_LONG", "BULLISH", "CALL", warnings
                return "SINGLE_LONG", "BEARISH", "PUT", warnings

        if len(all_legs) == 2:
            types = [l.get("instrument", {}).get("optionType") for l in all_legs]
            sides = [l.get("side") for l in all_legs]
            if "BUY" in sides and "SELL" in sides:
                if all(t == "PE" for t in types):
                    return "BULL_PUT_SPREAD", "BULLISH", "PUT", warnings
                if all(t == "CE" for t in types):
                    return "BEAR_CALL_SPREAD", "BEARISH", "CALL", warnings

        if len(all_legs) >= 4:
            sells = [l for l in all_legs if l.get("side") == "SELL"]
            buys = [l for l in all_legs if l.get("side") == "BUY"]
            if len(sells) >= 2 and len(buys) >= 2:
                warnings.append("STRUCTURE_DERIVED_FROM_LEGS:SHORT_STRANGLE->IRON_CONDOR")
                return "IRON_CONDOR", "NEUTRAL", "BOTH", warnings

        # Multiple cases with CE in one and PE in another
        if len(cases) > 1:
            return "SINGLE_LONG", "DYNAMIC", "BOTH", warnings

        return "CUSTOM_MULTI_LEG", "DYNAMIC", "BOTH", warnings

    def _map_legacy_category(self, def_type: str, code: str) -> str:
        t = (def_type or "").upper()
        c = code.lower()
        if "MOMENTUM" in t or "momentum" in c:
            return "MOMENTUM"
        if "BREAKOUT" in t or "BREAKDOWN" in t or "breakout" in c or "orb" in c:
            return "BREAKOUT"
        if "TREND" in t or "trend" in c:
            return "TREND"
        if "VWAP" in t or "vwap" in c:
            return "VWAP"
        if "SPREAD" in t or "STRANGLE" in t or "CONDOR" in t or "selling" in c or "theta" in c:
            return "PREMIUM_SELLING"
        return "OTHER"

    def _merge_legacy_rules(self, raw_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merges mirrored LIVE and PAPER rules into one rule with both domains."""
        merged: Dict[str, Dict[str, Any]] = {}

        for r in raw_rules:
            rule_id = r.get("rule_id") or r.get("code")
            base_code = rule_id.replace("-PAPER", "")

            if base_code not in merged:
                markets = [m.strip() for m in r.get("markets", "NIFTY,BANKNIFTY,SENSEX").split(",")]
                sides = [s.strip() for s in r.get("option_types", "CALL,PUT").split(",")]
                modes = [m.strip() for m in r.get("trading_modes", "INTRADAY,SHORT_TERM").split(",")]
                domains = [r.get("execution_domain", "LIVE")]

                merged[base_code] = {
                    "code": base_code,
                    "name": r.get("reason", base_code)[:150],
                    "ruleKind": "GUARDRAIL",
                    "ruleType": r.get("rule_type", "MARKET_REGIME"),
                    "action": r.get("action", "AVOID"),
                    "priority": r.get("priority", "HIGH"),
                    "appliesTo": {
                        "markets": markets,
                        "optionSides": sides,
                        "tradingModes": modes,
                        "executionDomains": domains,
                    },
                    "conditionText": r.get("condition_text", ""),
                    "content": {
                        "when": {
                            "left": {"source": "INDICATOR", "code": "MARKET_REGIME", "output": "value", "params": None},
                            "operator": "IN",
                            "right": {"const": ["RANGING", "SIDEWAYS", "BEARISH"]},
                        },
                        "unless": {
                            "op": "ALL",
                            "items": [
                                {
                                    "left": {"source": "INDICATOR", "code": "MARKET_REGIME", "output": "value", "params": None},
                                    "operator": "EQUALS",
                                    "right": {"const": "TRENDING_UP"},
                                },
                                {
                                    "left": {"source": "INDICATOR", "code": "ADX", "output": "adx", "params": None},
                                    "operator": "IS_ABOVE",
                                    "right": {"param": "minAdx"},
                                },
                                {
                                    "left": {"source": "PRICE", "field": "close", "bar": "CURRENT", "timeframe": None},
                                    "operator": "IS_ABOVE",
                                    "right": {"source": "INDICATOR", "code": "VWAP", "output": "currentDay", "params": None},
                                },
                            ],
                        },
                        "parameters": {"minAdx": 20},
                    },
                    "evidence": {
                        "count": r.get("evidence_count", 0),
                        "successRatePct": r.get("win_rate_success_rate_percent", 0),
                        "failureRatePct": r.get("failure_rate_percent", 0),
                    },
                    "executable": False,  # MARKET_REGIME has no handler yet
                    "provenance": {"source": "LEGACY_IMPORT", "legacy_ids": [rule_id]},
                    "reviewFlags": ["REGIME_DEPENDENT_EVIDENCE"],
                }
            else:
                # Add domain to existing merged rule
                dom = r.get("execution_domain")
                if dom and dom not in merged[base_code]["appliesTo"]["executionDomains"]:
                    merged[base_code]["appliesTo"]["executionDomains"].append(dom)
                merged[base_code]["provenance"]["legacy_ids"].append(rule_id)

        return list(merged.values())

    async def export_bundle(
        self,
        session: AsyncSession,
        request: ExportRequest,
    ) -> ExportResponse:
        strategies = await self.strategy_repo.list_all_active(session)
        if request.ids:
            strategies = [s for s in strategies if s.id in request.ids]

        rules = await self.rule_repo.get_active_guardrails(session)

        strats_out = []
        for s in strategies:
            v = s.versions[0] if s.versions else None
            snaps_out = []
            if request.includePerformance:
                for sn in s.performanceSnapshots:
                    snaps_out.append({
                        "source": sn.source,
                        "domain": sn.domain,
                        "totalTrades": sn.totalTrades,
                        "winningTrades": sn.winningTrades,
                        "losingTrades": sn.losingTrades,
                        "winRatePct": float(sn.winRatePct),
                        "netPnl": float(sn.netPnl),
                        "profitFactor": float(sn.profitFactor),
                        "maxDrawdown": float(sn.maxDrawdown),
                        "legacyHealth": sn.legacyHealth,
                        "reliabilityFlags": sn.reliabilityFlags,
                    })

            strats_out.append({
                "code": s.code,
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "structure": s.structure,
                "bias": s.bias,
                "optionSide": s.optionSide,
                "markets": s.markets,
                "underlyingTypes": s.underlyingTypes,
                "exchange": s.exchange,
                "tradingModes": s.tradingModes,
                "executionModes": s.executionModes,
                "timeframe": s.timeframe,
                "definitionFormat": s.definitionFormat,
                "lifecycleStatus": s.lifecycleStatus,
                "health": s.health,
                "validationStatus": s.validationStatus,
                "riskProfile": s.riskProfile,
                "references": s.references,
                "riskNotes": s.riskNotes,
                "howItWorks": s.howItWorks,
                "tags": s.tags,
                "attributes": s.attributes,
                "provenance": s.provenance,
                "reviewFlags": s.reviewFlags,
                "definition": v.definition if v else {},
                "performanceSnapshots": snaps_out,
            })

        rules_out = []
        for r in rules:
            v = r.versions[0] if r.versions else None
            rules_out.append({
                "code": r.code,
                "name": r.name,
                "ruleKind": r.ruleKind,
                "ruleType": r.ruleType,
                "action": r.action,
                "priority": r.priority,
                "appliesTo": r.appliesTo,
                "conditionText": r.conditionText,
                "evidence": r.evidence,
                "provenance": r.provenance,
                "reviewFlags": r.reviewFlags,
                "content": v.content if v else {},
            })

        return ExportResponse(
            schemaVersion=2,
            source="AUTO_TRADER_V2",
            exportedAt=datetime.now(),
            strategies=strats_out,
            rules=rules_out,
        )
