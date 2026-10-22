from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple
from app.modules.strategies.schema.strategy_schema import (
    AdjustmentEvalResult,
    ConditionEvalResult,
    EvaluateStrategyResponse,
)


class RuleEvaluator:
    """Evaluates rule trees, condition nodes, and guardrails against feature snapshots."""

    def evaluate_strategy(
        self,
        definition: Dict[str, Any],
        context: Dict[str, Any],
    ) -> EvaluateStrategyResponse:
        entry_met = False
        exit_met = False
        active_case_key = None
        conditions: List[ConditionEvalResult] = []
        adjustments_res: List[AdjustmentEvalResult] = []
        target_legs: List[Dict[str, Any]] = []

        format_val = definition.get("format", "RULE_TREE")
        if format_val != "RULE_TREE":
            return EvaluateStrategyResponse(
                entryMet=False,
                exitMet=False,
                activeCaseKey=None,
                conditions=[],
                adjustments=[],
                targetLegs=[],
            )

        cases = definition.get("cases", [])
        for case in cases:
            case_key = str(case.get("key", "0"))
            entry = case.get("entry", {})
            when_node = entry.get("when")

            case_entry_passed = True
            if when_node:
                case_entry_passed = self.evaluate_condition_node(
                    node=when_node,
                    context=context,
                    path=f"case[{case_key}].entry",
                    collected_conditions=conditions,
                )

            if case_entry_passed and not entry_met:
                entry_met = True
                active_case_key = case_key
                target_legs = entry.get("legs", [])

            # Exit condition
            exit_block = case.get("exit")
            if exit_block and isinstance(exit_block, dict):
                exit_when = exit_block.get("when")
                if exit_when:
                    case_exit_passed = self.evaluate_condition_node(
                        node=exit_when,
                        context=context,
                        path=f"case[{case_key}].exit",
                        collected_conditions=conditions,
                    )
                    if case_exit_passed:
                        exit_met = True

            # Adjustments
            for adj in case.get("adjustments", []):
                adj_key = str(adj.get("key", ""))
                adj_when = adj.get("when")
                triggered = False
                if adj_when:
                    triggered = self.evaluate_condition_node(
                        node=adj_when,
                        context=context,
                        path=f"case[{case_key}].adjustment[{adj_key}]",
                        collected_conditions=conditions,
                    )
                adjustments_res.append(
                    AdjustmentEvalResult(
                        key=adj_key,
                        triggered=triggered,
                        actions=adj.get("actions", []) if triggered else [],
                    )
                )

        return EvaluateStrategyResponse(
            entryMet=entry_met,
            exitMet=exit_met,
            activeCaseKey=active_case_key,
            conditions=conditions,
            adjustments=adjustments_res,
            targetLegs=target_legs,
        )

    def evaluate_condition_node(
        self,
        node: Dict[str, Any],
        context: Dict[str, Any],
        path: str = "",
        collected_conditions: Optional[List[ConditionEvalResult]] = None,
    ) -> bool:
        if not node or not isinstance(node, dict):
            return False

        # Group node: ALL, ANY, NOT
        if "op" in node:
            op = node.get("op", "ALL")
            items = node.get("items", [])
            if op == "ALL":
                for idx, child in enumerate(items):
                    if not self.evaluate_condition_node(
                        child, context, f"{path}.all[{idx}]", collected_conditions
                    ):
                        return False
                return True
            elif op == "ANY":
                any_passed = False
                for idx, child in enumerate(items):
                    passed = self.evaluate_condition_node(
                        child, context, f"{path}.any[{idx}]", collected_conditions
                    )
                    if passed:
                        any_passed = True
                return any_passed
            elif op == "NOT":
                if items:
                    child_res = self.evaluate_condition_node(
                        items[0], context, f"{path}.not", collected_conditions
                    )
                    return not child_res
                return True

        # Leaf condition
        left_op = node.get("left")
        operator = node.get("operator", "EQUALS")
        right_op = node.get("right")

        left_val = self.resolve_operand(left_op, context)
        right_val = self.resolve_operand(right_op, context)

        passed = self._apply_operator(left_op, left_val, operator, right_op, right_val, context)

        if collected_conditions is not None:
            left_desc = self._describe_operand(left_op)
            right_desc = self._describe_operand(right_op)
            cond_str = f"{left_desc} {operator} {right_desc}"
            collected_conditions.append(
                ConditionEvalResult(
                    path=path,
                    condition=cond_str,
                    passed=passed,
                    leftValue=left_val,
                    rightValue=right_val,
                )
            )

        return passed

    def resolve_operand(self, operand: Any, context: Dict[str, Any]) -> Any:
        if operand is None:
            return None
        if not isinstance(operand, dict):
            return operand

        if "const" in operand:
            return operand["const"]

        if "param" in operand:
            param_name = operand["param"]
            return context.get("parameters", {}).get(param_name, context.get(param_name))

        source = operand.get("source")
        if not source:
            return None

        if source == "PRICE":
            field = operand.get("field", "close")
            bar = operand.get("bar", "CURRENT")
            # If context has bar data
            prices = context.get("prices", {})
            if bar == "PREVIOUS":
                return prices.get("previous", {}).get(field)
            return prices.get("current", {}).get(field, context.get(field))

        if source == "DAY":
            day = operand.get("day", "TODAY")
            field = operand.get("field")
            day_data = context.get("days", {}).get(day, {})
            return day_data.get(field, context.get(field))

        if source == "INDICATOR":
            code = operand.get("code")
            output = operand.get("output", "value")
            ind_data = context.get("indicators", {}).get(code)
            if isinstance(ind_data, dict):
                return ind_data.get(output)
            return ind_data

        if source == "TIME":
            field = operand.get("field", "timeOfDay")
            return context.get("time", {}).get(field, context.get(field))

        if source == "CONTEXT":
            field = operand.get("field")
            return context.get("context", {}).get(field, context.get(field))

        if source == "POSITION":
            field = operand.get("field")
            case_key = operand.get("caseKey")
            leg_id = operand.get("legId")
            pos_data = context.get("positions", {}).get(f"{case_key}_{leg_id}", {})
            return pos_data.get(field, context.get(field))

        if source == "TRADE_PLAN":
            field = operand.get("field")
            return context.get("tradePlan", {}).get(field, context.get(field))

        return None

    def _apply_operator(
        self,
        left_op: Any,
        left_val: Any,
        operator: str,
        right_op: Any,
        right_val: Any,
        context: Dict[str, Any],
    ) -> bool:
        if left_val is None or right_val is None:
            # Special case: EQUALS or NOT_EQUALS with None
            if operator == "EQUALS":
                return left_val == right_val
            if operator == "NOT_EQUALS":
                return left_val != right_val
            return False

        # Rule 10: The EQUALS operator on a TIME operand means: the first evaluation at or after that time
        is_time_comparison = (
            isinstance(left_op, dict) and left_op.get("source") == "TIME"
        ) or (
            isinstance(right_op, dict) and right_op.get("type") == "TIME"
        )

        if is_time_comparison:
            try:
                t_left = self._parse_time(str(left_val))
                t_right = self._parse_time(str(right_val))
                if operator == "EQUALS":
                    # At or after the time
                    return t_left >= t_right
                if operator in ("IS_ABOVE", "CROSSES_ABOVE"):
                    return t_left > t_right
                if operator in ("IS_BELOW", "CROSSES_BELOW"):
                    return t_left < t_right
            except Exception:
                pass

        try:
            # Attempt numeric comparison
            num_left = float(left_val)
            num_right = float(right_val)
            if operator == "IS_ABOVE":
                return num_left > num_right
            if operator == "IS_ABOVE_OR_EQUAL":
                return num_left >= num_right
            if operator == "IS_BELOW":
                return num_left < num_right
            if operator == "IS_BELOW_OR_EQUAL":
                return num_left <= num_right
            if operator == "EQUALS":
                return abs(num_left - num_right) < 1e-9
            if operator == "NOT_EQUALS":
                return abs(num_left - num_right) >= 1e-9
        except (ValueError, TypeError):
            pass

        # String / Sequence / Set operations
        if operator == "EQUALS":
            return str(left_val) == str(right_val)
        if operator == "NOT_EQUALS":
            return str(left_val) != str(right_val)
        if operator == "IN":
            if isinstance(right_val, (list, tuple, set)):
                return str(left_val) in [str(x) for x in right_val]
            return str(left_val) in str(right_val)
        if operator == "NOT_IN":
            if isinstance(right_val, (list, tuple, set)):
                return str(left_val) not in [str(x) for x in right_val]
            return str(left_val) not in str(right_val)
        if operator == "BETWEEN":
            if isinstance(right_val, (list, tuple)) and len(right_val) >= 2:
                try:
                    return float(right_val[0]) <= float(left_val) <= float(right_val[1])
                except (ValueError, TypeError):
                    return str(right_val[0]) <= str(left_val) <= str(right_val[1])
            return False

        # CROSSES_ABOVE / CROSSES_BELOW
        if operator in ("CROSSES_ABOVE", "CROSSES_BELOW"):
            prev_left = context.get("previous", {}).get("left", left_val)
            prev_right = context.get("previous", {}).get("right", right_val)
            try:
                nl, nr = float(left_val), float(right_val)
                pnl, pnr = float(prev_left), float(prev_right)
                if operator == "CROSSES_ABOVE":
                    return pnl <= pnr and nl > nr
                if operator == "CROSSES_BELOW":
                    return pnl >= pnr and nl < nr
            except (ValueError, TypeError):
                pass
            return False

        return False

    def _parse_time(self, time_str: str) -> time:
        parts = time_str.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return time(h, m, s)

    def _describe_operand(self, operand: Any) -> str:
        if not operand or not isinstance(operand, dict):
            return str(operand)
        if "const" in operand:
            return str(operand["const"])
        if "param" in operand:
            return f"param({operand['param']})"
        source = operand.get("source", "")
        if source == "PRICE":
            return f"{source}.{operand.get('field', 'close')}"
        if source == "INDICATOR":
            return f"{operand.get('code')}.{operand.get('output', 'value')}"
        if source == "TIME":
            return "timeOfDay"
        if source == "DAY":
            return f"{operand.get('day')}.{operand.get('field')}"
        return f"{source}.{operand.get('field', '')}"
