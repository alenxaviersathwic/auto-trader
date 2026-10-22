from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.strategies.repository.rule_repository import RuleRepository
from app.modules.strategies.repository.strategy_repository import StrategyRepository
from app.modules.strategies.service.structure_analyzer import StructureAnalyzer


class ConflictAnalyzer:
    """
    Analyzes trading strategies and rules for conflicts against:
    - Active guardrails (AVOID, BLOCK, REQUIRE)
    - Internal condition contradictions (e.g. RSI > 70 and RSI < 30)
    - Time window errors and market hour mismatches
    - Undefined risk selling structures
    - Rule-on-rule priority contradictions
    """

    def __init__(
        self,
        strategy_repo: Optional[StrategyRepository] = None,
        rule_repo: Optional[RuleRepository] = None,
    ):
        self.strategy_repo = strategy_repo or StrategyRepository()
        self.rule_repo = rule_repo or RuleRepository()

    async def analyze_conflicts(
        self,
        session: AsyncSession,
        kind: str,  # "STRATEGY" or "RULE"
        definition: Dict[str, Any],
        meta: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        conflicts: List[Dict[str, Any]] = []
        meta = meta or {}

        if kind == "RULE":
            await self._analyze_rule_conflicts(session, definition, meta, conflicts)
        else:
            await self._analyze_strategy_conflicts(session, definition, meta, conflicts)

        return conflicts

    async def _analyze_strategy_conflicts(
        self,
        session: AsyncSession,
        definition: Dict[str, Any],
        meta: Dict[str, Any],
        conflicts: List[Dict[str, Any]],
    ) -> None:
        cases = definition.get("cases", [])
        if not cases:
            return

        first_case = cases[0]
        entry = first_case.get("entry", {})
        when_block = entry.get("when", {})
        conds = when_block.get("items", [])
        legs = entry.get("legs", [])
        exit_block = first_case.get("exit", {})
        time_win = first_case.get("timeWindow", {})

        # 1. Check Condition Count (overfitting risk)
        if len(conds) > 8:
            conflicts.append({
                "code": "TOO_MANY_CONDITIONS",
                "severity": "INFO",
                "message": f"Strategy defines {len(conds)} entry conditions, which poses an overfitting risk.",
                "path": "cases[0].entry.when.items",
            })

        # 2. Check Contradictory Conditions (e.g. RSI > 70 AND RSI < 30)
        self._check_condition_contradictions(conds, conflicts)

        # 3. Check Time Window Validity
        start = time_win.get("entryStart")
        end = time_win.get("entryEnd")
        exit_by = time_win.get("exitBy")
        if start and exit_by and start >= exit_by:
            conflicts.append({
                "code": "TIME_WINDOW_INVALID",
                "severity": "BLOCKER",
                "message": f"Entry start time ({start}) is at or after exit time ({exit_by}).",
                "path": "cases[0].timeWindow",
                "resolutions": ["Set entryStart earlier than exitBy"],
            })
        if end and exit_by and end > exit_by:
            conflicts.append({
                "code": "TIME_WINDOW_INVALID",
                "severity": "BLOCKER",
                "message": f"Entry end cutoff ({end}) is after exit time ({exit_by}).",
                "path": "cases[0].timeWindow",
                "resolutions": ["Set entryEnd before or equal to exitBy"],
            })

        # 4. Check Market Hours Mismatch
        market = meta.get("market") or (meta.get("markets", [None])[0] if meta.get("markets") else None)
        if market:
            m_upper = market.upper()
            is_commodity = any(c in m_upper for c in ["CRUDE", "GOLD", "SILVER", "COPPER", "NATURALGAS", "MCX"])
            if is_commodity and start and "09:15" in start and exit_by and "15:30" in exit_by:
                conflicts.append({
                    "code": "MARKET_HOURS_MISMATCH",
                    "severity": "WARNING",
                    "message": f"Commodity strategy for {market} uses equity index hours ({start}-{exit_by}) instead of MCX evening hours (09:00-23:30).",
                    "path": "cases[0].timeWindow",
                    "resolutions": ["Adjust time window to MCX market session (e.g., exit by 23:15:00)"],
                })

        # 5. Check Exits and Stops Defined
        has_exit_signal = exit_block.get("when") is not None
        has_market_close = exit_block.get("marketClose", False) is True
        has_time_exit = exit_by is not None
        has_leg_stops = any(leg.get("stopLoss") is not None for leg in legs)
        has_leg_targets = any(leg.get("target") is not None for leg in legs)

        if not (has_exit_signal or has_market_close or has_time_exit or has_leg_stops or has_leg_targets):
            conflicts.append({
                "code": "NO_EXIT_DEFINED",
                "severity": "BLOCKER",
                "message": "Strategy has no exit signal, time exit, stop loss, or profit target defined.",
                "path": "cases[0].exit",
                "resolutions": ["Add a stop loss %", "Add a time exit (e.g., 15:10:00)", "Add an exit condition"],
            })

        # Check Long option with no stop (time exit only)
        has_long_option = any(leg.get("side") == "BUY" and leg.get("instrument", {}).get("kind") == "OPTION" for leg in legs)
        if has_long_option and not has_leg_stops:
            conflicts.append({
                "code": "NO_STOP_DEFINED",
                "severity": "WARNING",
                "message": "Long option leg has no explicit stop loss defined (relies only on time exit / expiration).",
                "path": "cases[0].entry.legs",
                "resolutions": ["Add a stop loss (e.g., 25% of entry premium)"],
            })

        # 6. Check Structure and Undefined Risk
        structure_info = StructureAnalyzer.analyze(definition)
        if structure_info.get("riskType") == "UNDEFINED_RISK":
            conflicts.append({
                "code": "UNDEFINED_RISK",
                "severity": "BLOCKER",
                "message": "Option structure contains naked/unhedged short legs with no stop loss defined.",
                "path": "cases[0].entry.legs",
                "resolutions": [
                    "Add protective long hedge legs (convert to Iron Condor or Credit Spread)",
                    "Add explicit stop loss orders to all short legs",
                ],
            })

        # 7. Check Active Guardrails
        try:
            active_rules = await self.rule_repo.get_active_rules(session)
            strat_markets = set(meta.get("markets", []))
            if market:
                strat_markets.add(market)

            for rule in active_rules:
                if not rule.enabled:
                    continue
                rule_def = rule.definition or {}
                scope = rule_def.get("scope", {})
                rule_markets = set(scope.get("markets", []))

                # Check if scopes intersect
                if not rule_markets or (strat_markets and rule_markets.intersection(strat_markets)):
                    action = rule.action or rule_def.get("action", "AVOID")
                    if action in ["AVOID", "BLOCK", "REQUIRE"]:
                        conflicts.append({
                            "code": "CONFLICTS_WITH_GUARDRAIL",
                            "severity": "WARNING",
                            "message": f"Active guardrail '{rule.code}' (Action: {action}) applies to scope [{', '.join(strat_markets)}]. Message: {rule.description or ''}",
                            "ruleCode": rule.code,
                            "scope": list(rule_markets) if rule_markets else ["GLOBAL"],
                            "resolutions": [f"Review requirements for rule '{rule.code}' before deploying"],
                        })
        except Exception:
            # Safe fallback if tables not yet populated
            pass

    async def _analyze_rule_conflicts(
        self,
        session: AsyncSession,
        definition: Dict[str, Any],
        meta: Dict[str, Any],
        conflicts: List[Dict[str, Any]],
    ) -> None:
        action = meta.get("action") or definition.get("action", "AVOID")
        scope = definition.get("scope", {})
        rule_markets = set(scope.get("markets", []))

        try:
            active_rules = await self.rule_repo.get_active_rules(session)
            for existing in active_rules:
                if existing.code == meta.get("code"):
                    continue
                e_def = existing.definition or {}
                e_scope = e_def.get("scope", {})
                e_markets = set(e_scope.get("markets", []))

                if not rule_markets or not e_markets or rule_markets.intersection(e_markets):
                    e_action = existing.action or e_def.get("action")
                    if (action == "BLOCK" and e_action == "REQUIRE") or (action == "REQUIRE" and e_action == "BLOCK"):
                        conflicts.append({
                            "code": "RULE_CONFLICT",
                            "severity": "BLOCKER",
                            "message": f"New rule action {action} directly contradicts existing active rule '{existing.code}' with action {e_action}.",
                            "ruleCode": existing.code,
                            "resolutions": ["Modify action or deactivate contradictory rule"],
                        })
        except Exception:
            pass

    def _check_condition_contradictions(self, items: List[Dict[str, Any]], conflicts: List[Dict[str, Any]]) -> None:
        # Group numeric threshold conditions by operand key
        by_operand: Dict[str, List[Dict[str, Any]]] = {}
        for it in items:
            left = it.get("left", {})
            op = it.get("operator", "")
            right = it.get("right", {})
            if left.get("source") == "INDICATOR" and "const" in right:
                key = f"{left.get('code')}_{json.dumps(left.get('params', {}), sort_keys=True)}"
                by_operand.setdefault(key, []).append({
                    "operator": op,
                    "val": float(right["const"]) if isinstance(right["const"], (int, float)) else None,
                })

        for key, cond_list in by_operand.items():
            above_vals = [c["val"] for c in cond_list if c["operator"] in ["IS_ABOVE", "GREATER_THAN"] and c["val"] is not None]
            below_vals = [c["val"] for c in cond_list if c["operator"] in ["IS_BELOW", "LESS_THAN"] and c["val"] is not None]

            if above_vals and below_vals:
                min_above = min(above_vals)
                max_below = max(below_vals)
                if min_above >= max_below:
                    conflicts.append({
                        "code": "CONTRADICTION",
                        "severity": "BLOCKER",
                        "message": f"Contradictory conditions for {key.split('_')[0]}: requires above {min_above} AND below {max_below}, which can never be satisfied.",
                        "path": "cases[0].entry.when.items",
                        "resolutions": ["Correct the threshold parameters to a valid non-overlapping range"],
                    })
