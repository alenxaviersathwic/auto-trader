import re
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.strategies.repository.rule_repository import RuleRepository
from app.modules.strategies.repository.strategy_repository import StrategyRepository
from app.modules.strategies.service.strategy_explainer import StrategyExplainer


class SimilarityService:
    """
    Computes structural and condition similarity between strategies or rules.
    Detects DUPLICATE_OF (>= 90%) and OVERLAPS_WITH (60-89%).
    """

    def __init__(
        self,
        strategy_repo: Optional[StrategyRepository] = None,
        rule_repo: Optional[RuleRepository] = None,
    ):
        self.strategy_repo = strategy_repo or StrategyRepository()
        self.rule_repo = rule_repo or RuleRepository()

    async def find_similar_strategies(
        self,
        session: AsyncSession,
        definition: Dict[str, Any],
        meta: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        meta = meta or {}
        incoming_conditions = self._extract_normalized_conditions(definition)
        incoming_indicators = self._extract_indicator_codes(definition)
        incoming_structure = meta.get("structure")
        incoming_market = meta.get("market") or (meta.get("markets", [None])[0] if meta.get("markets") else None)

        strategies, _ = await self.strategy_repo.search(session, page=0, limit=50)

        results: List[Dict[str, Any]] = []
        for strat in strategies:
            if meta.get("code") and strat.code == meta.get("code"):
                continue

            strat_def = strat.definition or {}
            strat_conds = self._extract_normalized_conditions(strat_def)
            strat_inds = self._extract_indicator_codes(strat_def)

            # Compute Jaccard condition overlap
            overlap_conds = incoming_conditions.intersection(strat_conds)
            union_conds = incoming_conditions.union(strat_conds)

            cond_sim = len(overlap_conds) / len(union_conds) if union_conds else 0.0

            # Indicator overlap
            ind_overlap = incoming_indicators.intersection(strat_inds)
            ind_union = incoming_indicators.union(strat_inds)
            ind_sim = len(ind_overlap) / len(ind_union) if ind_union else 0.0

            # Market & Structure match
            market_match = 1.0 if incoming_market and strat.markets and incoming_market in strat.markets else 0.5
            struct_match = 1.0 if incoming_structure and strat.structure == incoming_structure else 0.5

            total_sim_pct = round(
                (cond_sim * 0.5 + ind_sim * 0.25 + market_match * 0.15 + struct_match * 0.1) * 100, 1
            )

            if total_sim_pct >= 40.0:
                results.append({
                    "code": strat.code,
                    "name": strat.name,
                    "similarityPct": total_sim_pct,
                    "overlappingConditions": list(overlap_conds),
                })

        results.sort(key=lambda x: x["similarityPct"], reverse=True)
        return results[:top_k]

    async def find_similar_rules(
        self,
        session: AsyncSession,
        definition: Dict[str, Any],
        meta: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        meta = meta or {}
        incoming_conditions = self._extract_normalized_conditions(definition.get("trigger", {}))
        rules, _ = await self.rule_repo.search(session, page=0, limit=50)

        results: List[Dict[str, Any]] = []
        for r in rules:
            if meta.get("code") and r.code == meta.get("code"):
                continue
            r_def = r.definition or {}
            r_conds = self._extract_normalized_conditions(r_def.get("trigger", {}))

            overlap = incoming_conditions.intersection(r_conds)
            union = incoming_conditions.union(r_conds)
            sim = len(overlap) / len(union) if union else 0.0
            sim_pct = round(sim * 100, 1)

            if sim_pct >= 40.0:
                results.append({
                    "code": r.code,
                    "name": r.name,
                    "similarityPct": sim_pct,
                    "overlappingConditions": list(overlap),
                })

        results.sort(key=lambda x: x["similarityPct"], reverse=True)
        return results[:top_k]

    def _extract_normalized_conditions(self, definition_or_group: Dict[str, Any]) -> Set[str]:
        conditions: Set[str] = set()
        if not definition_or_group or not isinstance(definition_or_group, dict):
            return conditions

        cases = definition_or_group.get("cases", [])
        if cases:
            for c in cases:
                when = c.get("entry", {}).get("when", {})
                for item in when.get("items", []):
                    conditions.add(StrategyExplainer._format_single_condition(item).lower())
        else:
            items = definition_or_group.get("items", [])
            for item in items:
                conditions.add(StrategyExplainer._format_single_condition(item).lower())

        return conditions

    def _extract_indicator_codes(self, definition: Dict[str, Any]) -> Set[str]:
        indicators: Set[str] = set()
        cases = definition.get("cases", [])
        for c in cases:
            when = c.get("entry", {}).get("when", {})
            for item in when.get("items", []):
                left = item.get("left", {})
                if left.get("source") == "INDICATOR":
                    code = left.get("code")
                    if code:
                        indicators.add(code.upper())
        return indicators
