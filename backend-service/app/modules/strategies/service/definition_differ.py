import json
from typing import Any, Dict, List, Optional
from app.modules.strategies.service.strategy_explainer import StrategyExplainer


class DefinitionDiffer:
    """
    Computes a structured diff and human-readable sentences between two strategy or rule definitions.
    """

    @classmethod
    def diff(cls, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        before = before or {}
        after = after or {}

        sentences: List[str] = []
        changed_paths: List[str] = []
        added_conditions: List[str] = []
        removed_conditions: List[str] = []
        leg_changes: List[str] = []
        param_changes: Dict[str, Any] = {}

        # 1. Format check
        fmt_before = before.get("format", "RULE_TREE")
        fmt_after = after.get("format", "RULE_TREE")
        if fmt_before != fmt_after:
            changed_paths.append("format")
            sentences.append(f"Definition format changed from {fmt_before} to {fmt_after}.")

        # 2. Cases comparison
        cases_before = before.get("cases", [])
        cases_after = after.get("cases", [])

        if len(cases_before) != len(cases_after):
            changed_paths.append("cases.length")
            sentences.append(f"Number of execution cases changed from {len(cases_before)} to {len(cases_after)}.")

        # Compare primary cases
        if cases_before and cases_after:
            c_b = cases_before[0]
            c_a = cases_after[0]

            # Conditions
            conds_b = cls._extract_conditions(c_b.get("entry", {}).get("when", {}))
            conds_a = cls._extract_conditions(c_a.get("entry", {}).get("when", {}))

            b_set = set(conds_b)
            a_set = set(conds_a)

            for c in a_set - b_set:
                added_conditions.append(c)
                sentences.append(f"Added entry condition: {c}")
            for c in b_set - a_set:
                removed_conditions.append(c)
                sentences.append(f"Removed entry condition: {c}")

            # Legs
            legs_b = c_b.get("entry", {}).get("legs", [])
            legs_a = c_a.get("entry", {}).get("legs", [])
            if len(legs_b) != len(legs_a):
                leg_changes.append(f"Leg count changed from {len(legs_b)} to {len(legs_a)}")
                sentences.append(f"Leg count changed from {len(legs_b)} to {len(legs_a)}.")
            else:
                for idx, (lb, la) in enumerate(zip(legs_b, legs_a)):
                    desc_b = StrategyExplainer._format_leg(lb)
                    desc_a = StrategyExplainer._format_leg(la)
                    if desc_b != desc_a:
                        leg_changes.append(f"Leg {idx + 1}: changed from [{desc_b}] to [{desc_a}]")
                        sentences.append(f"Updated Leg {idx + 1}: now {desc_a}.")

                    # Stops & Targets
                    sl_b = lb.get("stopLoss")
                    sl_a = la.get("stopLoss")
                    if sl_b != sl_a:
                        leg_changes.append(f"Leg {idx + 1} stop changed")
                        sentences.append(f"Leg {idx + 1} stop changed from {StrategyExplainer._format_stop(sl_b) if sl_b else 'None'} to {StrategyExplainer._format_stop(sl_a) if sl_a else 'None'}.")

                    tgt_b = lb.get("target")
                    tgt_a = la.get("target")
                    if tgt_b != tgt_a:
                        leg_changes.append(f"Leg {idx + 1} target changed")
                        sentences.append(f"Leg {idx + 1} target changed from {StrategyExplainer._format_target(tgt_b) if tgt_b else 'None'} to {StrategyExplainer._format_target(tgt_a) if tgt_a else 'None'}.")

            # Time window
            tw_b = c_b.get("timeWindow", {})
            tw_a = c_a.get("timeWindow", {})
            if tw_b != tw_a:
                changed_paths.append("timeWindow")
                sentences.append(f"Time window updated: start={tw_a.get('entryStart')}, end={tw_a.get('entryEnd')}, exitBy={tw_a.get('exitBy')}.")

        # 3. Parameters
        params_b = before.get("parameters", {})
        params_a = after.get("parameters", {})
        all_param_keys = set(params_b.keys()) | set(params_a.keys())
        for k in all_param_keys:
            vb = params_b.get(k)
            va = params_a.get(k)
            if vb != va:
                param_changes[k] = {"before": vb, "after": va}
                sentences.append(f"Parameter '{k}' changed from {vb} to {va}.")

        if not sentences:
            sentences.append("No material differences detected between definitions.")

        return {
            "changedPaths": changed_paths,
            "addedConditions": added_conditions,
            "removedConditions": removed_conditions,
            "legChanges": leg_changes,
            "paramChanges": param_changes,
            "sentences": sentences,
        }

    @classmethod
    def _extract_conditions(cls, when_block: Dict[str, Any]) -> List[str]:
        if not when_block or not isinstance(when_block, dict):
            return []
        items = when_block.get("items", [])
        results = []
        for it in items:
            results.append(StrategyExplainer._format_single_condition(it))
        return results
