import hashlib
import json
import os
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging.logger import logger
from app.modules.strategies.entity.health_policy_entity import HealthPolicy
from app.modules.strategies.entity.registry_item_entity import RegistryItem
from app.modules.strategies.entity.rule_entity import Rule
from app.modules.strategies.entity.rule_version_entity import RuleVersion
from app.modules.strategies.entity.strategy_entity import Strategy
from app.modules.strategies.entity.strategy_performance_snapshot_entity import StrategyPerformanceSnapshot
from app.modules.strategies.entity.strategy_version_entity import StrategyVersion
from app.modules.strategies.repository.health_repository import HealthRepository
from app.modules.strategies.repository.registry_repository import RegistryRepository
from app.modules.strategies.repository.rule_repository import RuleRepository
from app.modules.strategies.repository.strategy_repository import StrategyRepository
from app.modules.strategies.service.definition_validator import DefinitionValidator
from app.modules.strategies.service.reliability_calculator import ReliabilityCalculator


class SeedService:
    """Seeds initial registry items, default health policy, textbook strategies, and legacy strategies."""

    def __init__(
        self,
        registry_repo: Optional[RegistryRepository] = None,
        health_repo: Optional[HealthRepository] = None,
        strategy_repo: Optional[StrategyRepository] = None,
        rule_repo: Optional[RuleRepository] = None,
        validator: Optional[DefinitionValidator] = None,
        reliability_calc: Optional[ReliabilityCalculator] = None,
    ):
        self.registry_repo = registry_repo or RegistryRepository()
        self.health_repo = health_repo or HealthRepository()
        self.strategy_repo = strategy_repo or StrategyRepository()
        self.rule_repo = rule_repo or RuleRepository()
        self.validator = validator or DefinitionValidator()
        self.reliability_calc = reliability_calc or ReliabilityCalculator()

    async def seed_defaults(self, session: AsyncSession) -> Dict[str, Any]:
        """Loads registries, default health policy, 15 textbook strategies, legacy strategies/rules,
        and the Oct-2026 research-backed strategy/guardrail registry."""
        logger.info("Starting seed_defaults execution...")

        # 1. Seed Registries
        reg_count = await self._seed_registries(session)

        # 2. Seed Default Health Policy
        hp_count = await self._seed_health_policy(session)

        # 3. Seed 15 Textbook Strategies
        tb_count = await self._seed_textbook_strategies(session)

        # 4. Seed Legacy Strategies and Rules
        leg_strat_count, leg_rule_count = await self._seed_legacy_data(session)

        # 5. Seed Oct-2026 research registry (intraday index-option / MCX strategies + guardrails)
        res_strat_count, res_rule_count = await self._seed_research_data(session)

        return {
            "registriesSeeded": reg_count,
            "healthPoliciesSeeded": hp_count,
            "textbookStrategiesSeeded": tb_count,
            "legacyStrategiesSeeded": leg_strat_count,
            "rulesSeeded": leg_rule_count,
            "researchStrategiesSeeded": res_strat_count,
            "researchRulesSeeded": res_rule_count,
        }

    async def _seed_research_data(self, session: AsyncSession) -> Tuple[int, int]:
        """Seeds the strategy registry and guardrail rules from the Oct-2026 Claude research run
        (task wf-73cd02ba-57fd-81e6-bc87-e3915505046a): intraday index-option / MCX commodity
        strategies with activeDays scheduling, and the Section-4 guardrail rules. Idempotent by code,
        same pattern as _seed_legacy_data."""
        seed_path = os.path.join(os.path.dirname(__file__), "data", "research_strategies_seed.json")
        if not os.path.exists(seed_path):
            logger.warning(f"Research seed file not found at {seed_path}")
            return 0, 0

        with open(seed_path, "r") as f:
            data = json.load(f)

        strat_count = 0
        rule_count = 0

        for s in data.get("strategies", []):
            code = s["code"]
            existing = await self.strategy_repo.get_by_code(session, code)
            if existing:
                continue
            definition = s["definition"]
            val_res = await self.validator.validate(session, definition, s.get("definitionFormat", "SUMMARY"))
            raw_def = json.dumps(definition, sort_keys=True)
            ch = hashlib.sha256(raw_def.encode("utf-8")).hexdigest()

            strat = Strategy(
                code=code,
                name=s["name"],
                description=s.get("description"),
                category=s["category"],
                structure=s.get("structure"),
                bias=s.get("bias"),
                optionSide=s.get("optionSide"),
                markets=s.get("markets", []),
                underlyingTypes=s.get("underlyingTypes", []),
                exchange=s.get("exchange"),
                tradingModes=s.get("tradingModes", []),
                executionModes=s.get("executionModes", []),
                timeframe=s.get("timeframe"),
                activeDays=s.get("activeDays", []),
                dayOverrides=s.get("dayOverrides", []),
                definitionFormat=s.get("definitionFormat", "SUMMARY"),
                executable=val_res.executable,
                lifecycleStatus=s.get("lifecycleStatus", "DRAFT"),
                health=s.get("health", "HEALTHY"),
                validationStatus=s.get("validationStatus", "UNTESTED"),
                enabled=s.get("enabled", True),
                riskProfile=s.get("riskProfile"),
                references=s.get("references"),
                riskNotes=s.get("riskNotes"),
                howItWorks=s.get("howItWorks"),
                tags=s.get("tags"),
                attributes=s.get("attributes"),
                provenance=s.get("provenance"),
            )
            saved_s = await self.strategy_repo.save(session, strat)

            v1 = StrategyVersion(
                strategyId=saved_s.id,
                versionNo=1,
                schemaVersion=2,
                definition=definition,
                contentHash=ch,
                changeNote="Seeded from Oct-2026 research run (task wf-73cd02ba-57fd-81e6-bc87-e3915505046a)",
            )
            await self.strategy_repo.save_version(session, v1)
            saved_s.currentVersionId = v1.id
            await self.strategy_repo.save(session, saved_s)
            strat_count += 1

        for r in data.get("rules", []):
            code = r["code"]
            existing_rule = await self.rule_repo.get_by_code(session, code)
            if existing_rule:
                continue
            rule = Rule(
                code=code,
                name=r["name"],
                ruleKind=r.get("ruleKind", "GUARDRAIL"),
                ruleType=r.get("ruleType", "OTHER"),
                action=r.get("action"),
                priority=r.get("priority", "MEDIUM"),
                appliesTo=r.get("appliesTo", {}),
                conditionText=r.get("conditionText", ""),
                evidence=r.get("evidence"),
                executable=r.get("executable", True),
                provenance=r.get("provenance"),
                enabled=r.get("enabled", True),
            )
            saved_r = await self.rule_repo.save(session, rule)

            v1r = RuleVersion(
                ruleId=saved_r.id,
                versionNo=1,
                content=r.get("content", {}),
                changeNote="Seeded from Oct-2026 research run (task wf-73cd02ba-57fd-81e6-bc87-e3915505046a)",
            )
            await self.rule_repo.save_version(session, v1r)
            saved_r.currentVersionId = v1r.id
            await self.rule_repo.save(session, saved_r)
            rule_count += 1

        return strat_count, rule_count

    async def _seed_registries(self, session: AsyncSession) -> int:
        count = 0
        items: List[Dict[str, Any]] = [
            # OPERATORS
            {"type": "OPERATOR", "code": "IS_ABOVE", "name": "Is Above (>)", "handler": "operator_handler"},
            {"type": "OPERATOR", "code": "IS_ABOVE_OR_EQUAL", "name": "Is Above or Equal (>=)", "handler": "operator_handler"},
            {"type": "OPERATOR", "code": "IS_BELOW", "name": "Is Below (<)", "handler": "operator_handler"},
            {"type": "OPERATOR", "code": "IS_BELOW_OR_EQUAL", "name": "Is Below or Equal (<=)", "handler": "operator_handler"},
            {"type": "OPERATOR", "code": "EQUALS", "name": "Equals (==)", "handler": "operator_handler"},
            {"type": "OPERATOR", "code": "NOT_EQUALS", "name": "Not Equals (!=)", "handler": "operator_handler"},
            {"type": "OPERATOR", "code": "BETWEEN", "name": "Between", "handler": "operator_handler"},
            {"type": "OPERATOR", "code": "IN", "name": "In List", "handler": "operator_handler"},
            {"type": "OPERATOR", "code": "NOT_IN", "name": "Not In List", "handler": "operator_handler"},
            {"type": "OPERATOR", "code": "CROSSES_ABOVE", "name": "Crosses Above", "handler": "operator_handler"},
            {"type": "OPERATOR", "code": "CROSSES_BELOW", "name": "Crosses Below", "handler": "operator_handler"},
            # OPERAND_SOURCE
            {"type": "OPERAND_SOURCE", "code": "PRICE", "name": "Bar Price (OHLCV)", "handler": "price_handler"},
            {"type": "OPERAND_SOURCE", "code": "DAY", "name": "Daily Level (PDH/PDL)", "handler": "day_handler"},
            {"type": "OPERAND_SOURCE", "code": "INDICATOR", "name": "Technical Indicator", "handler": "indicator_handler"},
            {"type": "OPERAND_SOURCE", "code": "TIME", "name": "Time of Day", "handler": "time_handler"},
            {"type": "OPERAND_SOURCE", "code": "CONTEXT", "name": "Market Context", "handler": "context_handler"},
            {"type": "OPERAND_SOURCE", "code": "POSITION", "name": "Live Position State", "handler": "position_handler"},
            {"type": "OPERAND_SOURCE", "code": "TRADE_PLAN", "name": "Trade Plan / Cost", "handler": "plan_handler"},
            {"type": "OPERAND_SOURCE", "code": "CONSTANT", "name": "Literal Constant", "handler": "const_handler"},
            {"type": "OPERAND_SOURCE", "code": "PARAM", "name": "Strategy Parameter", "handler": "param_handler"},
            # STRIKE_SELECTOR
            {"type": "STRIKE_SELECTOR", "code": "ATM_OFFSET", "name": "ATM Strike Offset", "handler": "strike_atm"},
            {"type": "STRIKE_SELECTOR", "code": "DELTA", "name": "Nearest Delta", "handler": "strike_delta"},
            {"type": "STRIKE_SELECTOR", "code": "PREMIUM", "name": "Nearest Premium", "handler": "strike_premium"},
            # STOP_TYPE & TARGET_TYPE
            {"type": "STOP_TYPE", "code": "PERCENT", "name": "Percentage Stop", "handler": "stop_pct"},
            {"type": "STOP_TYPE", "code": "AMOUNT", "name": "Total INR Amount", "handler": "stop_amt"},
            {"type": "STOP_TYPE", "code": "POINTS", "name": "Absolute Index Points", "handler": "stop_pts"},
            {"type": "TARGET_TYPE", "code": "PERCENT", "name": "Percentage Target", "handler": "target_pct"},
            {"type": "TARGET_TYPE", "code": "AMOUNT", "name": "Total INR Target", "handler": "target_amt"},
            {"type": "TARGET_TYPE", "code": "POINTS", "name": "Absolute Index Target", "handler": "target_pts"},
            # TRAIL_TYPE
            {"type": "TRAIL_TYPE", "code": "LINEAR", "name": "Linear Trailing Stop", "handler": "trail_linear"},
            # EXPIRY_CYCLE
            {"type": "EXPIRY_CYCLE", "code": "WEEKLY", "name": "Weekly Expiry", "handler": "expiry_weekly"},
            {"type": "EXPIRY_CYCLE", "code": "MONTHLY", "name": "Monthly Expiry", "handler": "expiry_monthly"},
            # LEG_ACTION
            {"type": "LEG_ACTION", "code": "OPEN_LEG", "name": "Open Leg", "handler": "action_open"},
            {"type": "LEG_ACTION", "code": "CLOSE_LEG", "name": "Close Leg", "handler": "action_close"},
            # STRUCTURE
            {"type": "STRUCTURE", "code": "SINGLE_LONG", "name": "Single Leg Long Option", "handler": "struct_long"},
            {"type": "STRUCTURE", "code": "BULL_PUT_SPREAD", "name": "Bull Put Credit Spread", "handler": "struct_spread"},
            {"type": "STRUCTURE", "code": "BEAR_CALL_SPREAD", "name": "Bear Call Credit Spread", "handler": "struct_spread"},
            {"type": "STRUCTURE", "code": "IRON_CONDOR", "name": "Iron Condor", "handler": "struct_condor"},
            {"type": "STRUCTURE", "code": "SHORT_STRANGLE", "name": "Short Strangle", "handler": "struct_strangle"},
            {"type": "STRUCTURE", "code": "CUSTOM_MULTI_LEG", "name": "Custom Multi-Leg Option", "handler": "struct_multi"},
            {"type": "STRUCTURE", "code": "MIXED", "name": "Mixed Strategy Structure", "handler": "struct_mixed"},
            # EVALUATORS (stored with no handler until implemented)
            {"type": "EVALUATOR", "code": "ORB15", "name": "15-Minute Opening Range Breakout Evaluator", "handler": None},
            {"type": "EVALUATOR", "code": "EMA_PULLBACK", "name": "EMA Trend Pullback Evaluator", "handler": None},
            # INDICATORS
            {"type": "INDICATOR", "code": "EMA", "name": "Exponential Moving Average", "handler": "ind_ema", "schema": {"params": {"period": {"type": "int", "default": 9}}}},
            {"type": "INDICATOR", "code": "SMA", "name": "Simple Moving Average", "handler": "ind_sma", "schema": {"params": {"period": {"type": "int", "default": 20}}}},
            {"type": "INDICATOR", "code": "RSI", "name": "Relative Strength Index", "handler": "ind_rsi", "schema": {"params": {"period": {"type": "int", "default": 14}}}},
            {"type": "INDICATOR", "code": "CCI", "name": "Commodity Channel Index", "handler": "ind_cci", "schema": {"params": {"period": {"type": "int", "default": 20}}}},
            {"type": "INDICATOR", "code": "ADX", "name": "Average Directional Index", "handler": "ind_adx", "schema": {"params": {"period": {"type": "int", "default": 14}}}, "outputs": ["adx", "plusDi", "minusDi"]},
            {"type": "INDICATOR", "code": "ATR", "name": "Average True Range", "handler": "ind_atr", "schema": {"params": {"period": {"type": "int", "default": 14}}}},
            {"type": "INDICATOR", "code": "SUPERTREND", "name": "Supertrend", "handler": "ind_supertrend", "schema": {"params": {"period": {"type": "int", "default": 10}, "multiplier": {"type": "float", "default": 3.0}}}},
            {"type": "INDICATOR", "code": "BBANDS", "name": "Bollinger Bands", "handler": "ind_bbands", "schema": {"params": {"period": {"type": "int", "default": 20}, "stdDev": {"type": "float", "default": 2.0}}}, "outputs": ["upper", "middle", "lower", "width"]},
            {"type": "INDICATOR", "code": "VWAP", "name": "Volume Weighted Average Price", "handler": "ind_vwap", "outputs": ["currentDay", "upperBand", "lowerBand"]},
            {"type": "INDICATOR", "code": "PIVOT_POINTS", "name": "Pivot Points (Standard / Camarilla)", "handler": "ind_pivots", "schema": {"params": {"variant": {"type": "str", "default": "STANDARD"}}}, "outputs": ["P", "R1", "R2", "R3", "R4", "S1", "S2", "S3", "S4"]},
            # MARKET_REGIME: stored with no handler, so rules using it are executable=false until classifier is built
            {"type": "INDICATOR", "code": "MARKET_REGIME", "name": "Market Regime Classifier", "handler": None, "outputs": ["value"]},
        ]

        for it in items:
            existing = await self.registry_repo.get_by_type_and_code(session, it["type"], it["code"])
            if not existing:
                item_obj = RegistryItem(
                    registryType=it["type"],
                    code=it["code"],
                    name=it["name"],
                    kind="BUILT_IN",
                    version=1,
                    schema=it.get("schema"),
                    handlerKey=it.get("handler"),
                    executable=bool(it.get("handler")),
                    description=it.get("name"),
                    enabled=True,
                )
                await self.registry_repo.save(session, item_obj)
                count += 1

        return count

    async def _seed_health_policy(self, session: AsyncSession) -> int:
        existing = await self.health_repo.get_policy_by_code(session, "DEFAULT")
        if not existing:
            hp = HealthPolicy(
                code="DEFAULT",
                name="Default Health Policy",
                scope="ALL",
                params={
                    "minTrades": 30,
                    "window": 30,
                    "suspendIfProfitFactorBelow": 0.8,
                    "degradeIfProfitFactorBelow": 1.0,
                    "suspendIfDrawdownAbove": 50000,
                    "suspendAfterConsecutiveLosses": 5,
                },
                enabled=True,
            )
            await self.health_repo.save_policy(session, hp)
            return 1
        return 0

    async def _seed_textbook_strategies(self, session: AsyncSession) -> int:
        """Seeds 15 textbook strategies in RULE_TREE format with default parameters."""
        textbook_codes = [
            ("ORB_15M", "15-Minute Opening Range Breakout", "MOMENTUM", "BULLISH", "CALL"),
            ("PDH_PDL_BREAK", "Previous Day High / Low Breakout", "BREAKOUT", "BULLISH", "CALL"),
            ("VWAP_RECLAIM", "VWAP Reclaim & Continuation", "VWAP", "BULLISH", "CALL"),
            ("EMA_PULLBACK", "9/21 EMA Trend Pullback", "TREND", "BULLISH", "CALL"),
            ("SUPERTREND_ADX", "Supertrend with ADX Confirmation", "TREND", "BULLISH", "CALL"),
            ("BB_SQUEEZE", "Bollinger Band Squeeze Breakout", "VOLATILITY", "BULLISH", "CALL"),
            ("INSIDE_BAR_BREAK", "Inside Bar Momentum Breakout", "BREAKOUT", "BULLISH", "CALL"),
            ("CPR_NARROW", "Central Pivot Range (CPR) Trend Reversal", "REVERSAL", "BULLISH", "CALL"),
            ("RSI_LEVEL_REVERSAL", "RSI Oversold Level Reversal", "REVERSAL", "BULLISH", "CALL"),
            ("OI_WALL_BOUNCE", "Open Interest Wall Support Bounce", "OI_BASED", "BULLISH", "CALL"),
            ("OI_BUILDUP_MOMENTUM", "Call/Put Unwinding & OI Buildup", "OI_BASED", "BULLISH", "CALL"),
            ("GAP_AND_GO", "Morning Gap & Go Trend Continuation", "MOMENTUM", "BULLISH", "CALL"),
            ("GAP_FADE", "Morning Gap Fade Mean Reversion", "REVERSAL", "BEARISH", "PUT"),
            ("EXPIRY_MOMENTUM", "Expiry Day Afternoon Momentum Spike", "MOMENTUM", "BULLISH", "CALL"),
            ("EVENT_REACTION", "Macro Event Blackout & Trend Reaction", "EVENT", "DYNAMIC", "BOTH"),
        ]

        count = 0
        for code, name, cat, bias, side in textbook_codes:
            existing = await self.strategy_repo.get_by_code(session, code)
            if not existing:
                definition = {
                    "schemaVersion": 2,
                    "format": "RULE_TREE",
                    "isParallelCases": False,
                    "cases": [
                        {
                            "key": "0",
                            "bias": bias,
                            "entry": {
                                "when": {
                                    "left": {"source": "PRICE", "field": "close", "bar": "CURRENT", "timeframe": "5m"},
                                    "operator": "IS_ABOVE",
                                    "right": {"source": "INDICATOR", "code": "VWAP", "output": "currentDay", "params": None},
                                },
                                "legs": [
                                    {
                                        "legId": "1",
                                        "side": "BUY",
                                        "instrument": {
                                            "kind": "OPTION",
                                            "optionType": "CE" if side in ("CALL", "BOTH") else "PE",
                                            "expiry": {"cycle": "WEEKLY", "index": 1},
                                            "strike": {"selector": "ATM_OFFSET", "steps": 0},
                                        },
                                        "quantity": {"unit": "LOT", "value": 1},
                                        "stopLoss": {"type": "PERCENT", "value": 20, "basis": "ENTRY_PREMIUM"},
                                        "target": {"type": "PERCENT", "value": 50, "basis": "ENTRY_PREMIUM"},
                                    }
                                ],
                            },
                            "exit": {
                                "when": {
                                    "left": {"source": "TIME", "field": "timeOfDay"},
                                    "operator": "EQUALS",
                                    "right": {"const": "15:14:00", "type": "TIME"},
                                }
                            },
                            "adjustments": [],
                            "extras": {},
                        }
                    ],
                    "bounds": {
                        "session": {"entryTime": "09:20", "exitTime": "15:14"},
                        "maxTradesPerDay": 3,
                        "dayStopLoss": {"type": "AMOUNT", "value": 3000},
                        "dayStopGain": {"type": "AMOUNT", "value": 6000},
                    },
                    "riskPolicy": {"stopMode": "STRATEGY_FIXED"},
                    "parameters": {"targetRr": 2.0},
                    "extras": {},
                }

                raw_def = json.dumps(definition, sort_keys=True)
                ch = hashlib.sha256(raw_def.encode("utf-8")).hexdigest()

                strat = Strategy(
                    code=code,
                    name=name,
                    description=f"Built-in textbook algorithmic trading strategy: {name}.",
                    category=cat,
                    structure="SINGLE_LONG",
                    bias=bias,
                    optionSide=side,
                    markets=["NIFTY", "BANKNIFTY"],
                    underlyingTypes=["INDEX"],
                    exchange="NSE",
                    tradingModes=["INTRADAY"],
                    executionModes=["PAPER", "LIVE"],
                    timeframe="5m",
                    definitionFormat="RULE_TREE",
                    executable=True,
                    lifecycleStatus="ACTIVE",
                    health="HEALTHY",
                    validationStatus="UNTESTED",
                    enabled=True,
                    riskProfile={"targetRr": 2.0, "maxRiskPct": 15},
                    howItWorks=[
                        {"title": "Entry Check", "description": "Verifies indicator threshold and entry criteria."},
                        {"title": "Risk Management", "description": "Strict 20% premium stop loss with fixed 1:2 risk-reward."},
                    ],
                    tags=["BUILT_IN", "TEXTBOOK", cat],
                    provenance={"source": "BUILT_IN"},
                )
                saved_s = await self.strategy_repo.save(session, strat)

                v1 = StrategyVersion(
                    strategyId=saved_s.id,
                    versionNo=1,
                    schemaVersion=2,
                    definition=definition,
                    contentHash=ch,
                    changeNote="Initial built-in version",
                )
                await self.strategy_repo.save_version(session, v1)
                saved_s.currentVersionId = v1.id
                await self.strategy_repo.save(session, saved_s)
                count += 1

        return count

    async def _seed_legacy_data(self, session: AsyncSession) -> Tuple[int, int]:
        """Seeds the 18 legacy strategies and 3 empirical rules from strategies_seed.json."""
        seed_path = os.path.join(os.path.dirname(__file__), "data", "strategies_seed.json")
        if not os.path.exists(seed_path):
            logger.warning(f"Seed file not found at {seed_path}")
            return 0, 0

        with open(seed_path, "r") as f:
            data = json.load(f)

        strat_count = 0
        rule_count = 0

        # Seed strategies
        for s in data.get("strategies", []):
            code = s["code"]
            existing = await self.strategy_repo.get_by_code(session, code)
            if not existing:
                definition = s["definition"]
                val_res = await self.validator.validate(session, definition, s.get("definitionFormat", "RULE_TREE"))
                raw_def = json.dumps(definition, sort_keys=True)
                ch = hashlib.sha256(raw_def.encode("utf-8")).hexdigest()

                strat = Strategy(
                    code=code,
                    name=s["name"],
                    description=s.get("description"),
                    category=s["category"],
                    structure=s.get("structure"),
                    bias=s.get("bias"),
                    optionSide=s.get("optionSide"),
                    markets=s.get("markets", []),
                    underlyingTypes=s.get("underlyingTypes", []),
                    exchange=s.get("exchange"),
                    tradingModes=s.get("tradingModes", []),
                    executionModes=s.get("executionModes", []),
                    timeframe=s.get("timeframe"),
                    definitionFormat=s.get("definitionFormat", "RULE_TREE"),
                    executable=val_res.executable,
                    lifecycleStatus=s.get("lifecycleStatus", "DRAFT"),
                    health=s.get("health", "HEALTHY"),
                    validationStatus=s.get("validationStatus", "UNTESTED"),
                    enabled=s.get("enabled", True),
                    riskProfile=s.get("riskProfile"),
                    references=s.get("references"),
                    riskNotes=s.get("riskNotes"),
                    howItWorks=s.get("howItWorks"),
                    tags=s.get("tags"),
                    attributes=s.get("attributes"),
                    provenance=s.get("provenance"),
                    reviewFlags=s.get("reviewFlags"),
                )
                saved_s = await self.strategy_repo.save(session, strat)

                v1 = StrategyVersion(
                    strategyId=saved_s.id,
                    versionNo=1,
                    schemaVersion=2,
                    definition=definition,
                    contentHash=ch,
                    changeNote="Legacy converted seed version",
                )
                await self.strategy_repo.save_version(session, v1)
                saved_s.currentVersionId = v1.id

                # Save snapshot
                for snap_data in s.get("performanceSnapshots", []):
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
                        strategyId=saved_s.id,
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

                await self.strategy_repo.save(session, saved_s)
                strat_count += 1

        # Seed rules
        for r in data.get("rules", []):
            code = r["code"]
            existing_rule = await self.rule_repo.get_by_code(session, code)
            if not existing_rule:
                rule = Rule(
                    code=code,
                    name=r["name"],
                    ruleKind=r.get("ruleKind", "GUARDRAIL"),
                    ruleType=r.get("ruleType", "OTHER"),
                    action=r.get("action"),
                    priority=r.get("priority", "MEDIUM"),
                    appliesTo=r.get("appliesTo", {}),
                    conditionText=r.get("conditionText", ""),
                    evidence=r.get("evidence"),
                    executable=r.get("executable", False),
                    reviewFlags=r.get("reviewFlags"),
                    provenance=r.get("provenance"),
                    enabled=r.get("enabled", True),
                )
                saved_r = await self.rule_repo.save(session, rule)

                v1 = RuleVersion(
                    ruleId=saved_r.id,
                    versionNo=1,
                    content=r.get("content", {}),
                    changeNote="Initial legacy rule version",
                )
                await self.rule_repo.save_version(session, v1)
                saved_r.currentVersionId = v1.id
                await self.rule_repo.save(session, saved_r)
                rule_count += 1

        return strat_count, rule_count
