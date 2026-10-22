from typing import Any, Dict, List, Optional, Union


class StrategyExplainer:
    """
    Deterministic definition-to-English renderer.
    Generates back-translations and clear explanations from structured definitions.
    Never uses an LLM.
    """

    @classmethod
    def explain(cls, definition: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> str:
        if not definition or not isinstance(definition, dict):
            return "Empty or invalid definition."

        fmt = definition.get("format", "RULE_TREE")
        if fmt == "SUMMARY":
            return cls._explain_summary(definition, meta)
        elif fmt == "EVALUATOR":
            return cls._explain_evaluator(definition, meta)
        else:
            return cls._explain_rule_tree(definition, meta)

    @classmethod
    def explain_rule(cls, definition: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> str:
        if not definition or not isinstance(definition, dict):
            return "Empty or invalid rule definition."

        paragraphs = []
        rule_kind = meta.get("ruleKind") if meta else definition.get("ruleKind", "GUARDRAIL")
        action = meta.get("action") if meta else definition.get("action", "AVOID")
        scope = definition.get("scope", {})

        scope_desc = cls._format_scope(scope)
        paragraphs.append(f"Rule Type: {rule_kind} | Action: {action} | Scope: {scope_desc}")

        trigger = definition.get("trigger", {})
        if trigger:
            conds_str = cls._format_condition_group(trigger)
            paragraphs.append(f"Trigger condition: When {conds_str}")

        effect = definition.get("effect", {})
        if effect:
            action_type = effect.get("action", action)
            message = effect.get("message", "")
            duration = effect.get("durationMinutes")
            dur_str = f" for {duration} minutes" if duration else ""
            paragraphs.append(f"Effect: Execute {action_type}{dur_str}. Alert: '{message}'")

        return "\n".join(paragraphs)

    @classmethod
    def _explain_summary(cls, definition: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> str:
        summary = definition.get("summary", {})
        entry_label = summary.get("entryLabel", "unspecified")
        indicators = summary.get("indicators", [])
        ind_str = ", ".join(indicators) if indicators else "none listed"
        return f"Summary definition: Entry based on '{entry_label}'. Indicators: {ind_str} (Descriptive only, not directly executable)."

    @classmethod
    def _explain_evaluator(cls, definition: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> str:
        evaluator = definition.get("evaluator", "custom_evaluator")
        config = definition.get("config", {})
        return f"Code Evaluator definition: Evaluated by handler '{evaluator}' with configuration: {config}."

    @classmethod
    def _explain_rule_tree(cls, definition: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> str:
        paragraphs: List[str] = []

        # Meta summary line if available
        if meta:
            market = meta.get("market") or (meta.get("markets", [None])[0] if meta.get("markets") else None)
            timeframe = meta.get("timeframe")
            structure = meta.get("structure")
            bias = meta.get("bias")
            parts = []
            if market:
                parts.append(f"Market: {market}")
            if structure:
                parts.append(f"Structure: {structure}")
            if bias:
                parts.append(f"Bias: {bias}")
            if timeframe:
                parts.append(f"Timeframe: {timeframe}")
            if parts:
                paragraphs.append(" | ".join(parts))

        cases = definition.get("cases", [])
        if not cases:
            return "No cases defined in strategy."

        is_parallel = definition.get("isParallelCases", False)
        if len(cases) > 1:
            case_mode = "parallel (all evaluated concurrently)" if is_parallel else "sequential (first matching case triggers)"
            paragraphs.append(f"Strategy evaluates {len(cases)} cases in {case_mode}:")

        for idx, case in enumerate(cases):
            case_label = case.get("label") or case.get("key", f"Case {idx + 1}")
            case_lines: List[str] = []

            # 1. Entry conditions
            entry = case.get("entry", {})
            entry_when = entry.get("when")
            if entry_when:
                cond_text = cls._format_condition_group(entry_when)
                case_lines.append(f"• Entry: When {cond_text}")
            else:
                case_lines.append("• Entry: Immediate / No entry condition specified")

            # 2. Legs to execute
            legs = entry.get("legs", [])
            if legs:
                leg_descriptions = [cls._format_leg(leg) for leg in legs]
                case_lines.append(f"• Execution Legs:\n  " + "\n  ".join(leg_descriptions))

            # 3. Exits and stops
            exit_blk = case.get("exit", {})
            exit_lines: List[str] = []
            exit_when = exit_blk.get("when")
            if exit_when:
                exit_lines.append(f"Exit when {cls._format_condition_group(exit_when)}")
            if exit_blk.get("marketClose"):
                exit_lines.append("Exit on market close (EOD square-off)")

            # Leg level stops & targets
            stops_targets: List[str] = []
            for leg in legs:
                leg_id = leg.get("legId", "1")
                sl = leg.get("stopLoss")
                tgt = leg.get("target")
                if sl:
                    stops_targets.append(f"Leg {leg_id} Stop: {cls._format_stop(sl)}")
                if tgt:
                    stops_targets.append(f"Leg {leg_id} Target: {cls._format_target(tgt)}")

            if stops_targets:
                exit_lines.extend(stops_targets)

            if exit_lines:
                case_lines.append(f"• Exits & Risk Controls:\n  " + "\n  ".join(f"- {el}" for el in exit_lines))

            # 4. Time Window
            tw = case.get("timeWindow")
            if tw:
                start = tw.get("entryStart", "09:15:00")
                end = tw.get("entryEnd", "15:00:00")
                exit_by = tw.get("exitBy")
                tw_str = f"• Trading Hours: Entries allowed between {start} and {end}"
                if exit_by:
                    tw_str += f", mandatory exit by {exit_by}"
                case_lines.append(tw_str)

            # 5. Adjustments
            adjustments = case.get("adjustments", [])
            if adjustments:
                adj_strs = [cls._format_adjustment(a) for a in adjustments]
                case_lines.append(f"• Adjustments:\n  " + "\n  ".join(adj_strs))

            if len(cases) > 1:
                paragraphs.append(f"[{case_label}]\n" + "\n".join(case_lines))
            else:
                paragraphs.append("\n".join(case_lines))

        return "\n\n".join(paragraphs)

    @classmethod
    def _format_scope(cls, scope: Dict[str, Any]) -> str:
        parts = []
        if scope.get("markets"):
            parts.append(f"markets: {', '.join(scope['markets'])}")
        if scope.get("underlyingTypes"):
            parts.append(f"underlyings: {', '.join(scope['underlyingTypes'])}")
        if scope.get("tradingModes"):
            parts.append(f"modes: {', '.join(scope['tradingModes'])}")
        return "; ".join(parts) if parts else "ALL"

    @classmethod
    def _format_condition_group(cls, group: Dict[str, Any]) -> str:
        op = group.get("op", "ALL").upper()
        items = group.get("items", [])
        if not items:
            return "always true"

        join_word = " AND " if op == "ALL" else " OR "
        formatted_items = [cls._format_single_condition(item) for item in items]
        if len(formatted_items) == 1:
            return formatted_items[0]
        return "(" + join_word.join(formatted_items) + ")"

    @classmethod
    def _format_single_condition(cls, cond: Dict[str, Any]) -> str:
        # Check if nested group
        if "items" in cond and "op" in cond:
            return cls._format_condition_group(cond)

        left = cls._format_operand(cond.get("left", {}))
        op = cls._format_operator(cond.get("operator", "EQUALS"))
        right = cls._format_right_operand(cond.get("right", {}))
        return f"{left} {op} {right}"

    @classmethod
    def _format_operand(cls, op: Dict[str, Any]) -> str:
        src = op.get("source", "UNKNOWN").upper()
        tf = op.get("timeframe")
        tf_prefix = f"{tf} " if tf else ""

        if src == "PRICE":
            field = op.get("field", "close").lower()
            bar = op.get("bar")
            bar_suffix = f" (bar {bar})" if bar else ""
            return f"{tf_prefix}{field}{bar_suffix}"

        if src == "INDICATOR":
            code = op.get("code", "INDICATOR").upper()
            params = op.get("params", {})
            output = op.get("output")
            param_str = ""
            if params:
                param_str = f"({', '.join(f'{k}={v}' for k, v in params.items())})"
            out_str = f".{output}" if output and output.lower() not in ["default", "value"] else ""
            return f"{tf_prefix}{code}{param_str}{out_str}"

        if src == "TIME":
            field = op.get("field", "timeOfDay")
            return f"Time of Day" if field == "timeOfDay" else f"Time ({field})"

        if src == "DAY":
            field = op.get("field", "close")
            return f"Previous Day {field.upper()}"

        if src == "CONTEXT":
            field = op.get("field", "context")
            return f"Market Context '{field}'"

        if src == "POSITION":
            field = op.get("field", "pnl")
            return f"Current Position {field.upper()}"

        if src == "PARAM":
            name = op.get("name", "param")
            return f"Parameter '{name}'"

        if src == "CONSTANT":
            val = op.get("value")
            return str(val)

        return f"{src}:{op.get('field', op.get('code', 'val'))}"

    @classmethod
    def _format_operator(cls, op: str) -> str:
        op_map = {
            "IS_ABOVE": "is above",
            "GREATER_THAN": "is above",
            "IS_ABOVE_OR_EQUAL": "is above or equal to",
            "GREATER_THAN_OR_EQUAL": "is above or equal to",
            "IS_BELOW": "is below",
            "LESS_THAN": "is below",
            "IS_BELOW_OR_EQUAL": "is below or equal to",
            "LESS_THAN_OR_EQUAL": "is below or equal to",
            "EQUALS": "equals",
            "NOT_EQUALS": "does not equal",
            "CROSSES_ABOVE": "crosses above",
            "CROSSES_BELOW": "crosses below",
            "BETWEEN": "is between",
            "IN": "is in",
            "NOT_IN": "is not in",
        }
        return op_map.get(op.upper(), op.lower().replace("_", " "))

    @classmethod
    def _format_right_operand(cls, right: Dict[str, Any]) -> str:
        if "const" in right:
            return str(right["const"])
        if "value" in right:
            return str(right["value"])
        if "source" in right:
            return cls._format_operand(right)
        return str(right)

    @classmethod
    def _format_leg(cls, leg: Dict[str, Any]) -> str:
        leg_id = leg.get("legId", "1")
        side = leg.get("side", "BUY").upper()
        qty = leg.get("quantity", {})
        qty_str = f"{qty.get('value', 1)} {qty.get('unit', 'LOT')}"

        inst = leg.get("instrument", {})
        kind = inst.get("kind", "EQUITY").upper()

        if kind == "OPTION":
            opt_type = "Call (CE)" if inst.get("optionType") == "CE" else "Put (PE)"
            exp = inst.get("expiry", {})
            exp_str = f"{exp.get('cycle', 'WEEKLY')} expiry (T+{exp.get('index', 1)})"
            strike = inst.get("strike", {})
            sel = strike.get("selector", "ATM")
            if sel == "ATM":
                strike_str = "ATM strike"
            elif sel == "ATM_OFFSET":
                steps = strike.get("steps", 0)
                if steps == 0:
                    strike_str = "ATM strike"
                elif steps > 0:
                    strike_str = f"OTM (+{steps} strikes) strike"
                else:
                    strike_str = f"ITM ({steps} strikes) strike"
            elif sel == "DELTA":
                strike_str = f"Delta {strike.get('delta', 50)}"
            else:
                strike_str = f"Strike selector: {sel}"

            return f"Leg {leg_id}: {side} {qty_str} of {exp_str} {strike_str} {opt_type}"

        elif kind == "FUTURE":
            exp = inst.get("expiry", {})
            exp_str = exp.get("cycle", "CURRENT_MONTH")
            return f"Leg {leg_id}: {side} {qty_str} of Futures ({exp_str})"

        else:
            return f"Leg {leg_id}: {side} {qty_str} of Cash / Underlying"

    @classmethod
    def _format_stop(cls, sl: Dict[str, Any]) -> str:
        sl_type = sl.get("type", "PERCENT").upper()
        val = sl.get("value")
        basis = sl.get("basis", "ENTRY_PREMIUM")
        if sl_type == "PERCENT":
            return f"{val}% stop loss on {basis.lower().replace('_', ' ')}"
        elif sl_type == "POINTS":
            return f"{val} points stop loss"
        elif sl_type == "AMOUNT":
            return f"₹{val} max loss stop"
        return f"{sl_type} stop ({val})"

    @classmethod
    def _format_target(cls, tgt: Dict[str, Any]) -> str:
        tgt_type = tgt.get("type", "PERCENT").upper()
        val = tgt.get("value")
        basis = tgt.get("basis", "ENTRY_PREMIUM")
        if tgt_type == "PERCENT":
            return f"{val}% target on {basis.lower().replace('_', ' ')}"
        elif tgt_type == "POINTS":
            return f"{val} points target"
        elif tgt_type == "AMOUNT":
            return f"₹{val} profit target"
        return f"{tgt_type} target ({val})"

    @classmethod
    def _format_adjustment(cls, adj: Dict[str, Any]) -> str:
        key = adj.get("key", "adjustment")
        trigger = adj.get("trigger", {})
        actions = adj.get("actions", [])
        trig_str = cls._format_condition_group(trigger) if trigger else "custom trigger"
        act_strs = [f"{a.get('type', 'ACTION')}: {a.get('legId', '')}" for a in actions]
        return f"Adjustment '{key}': When {trig_str} -> Do {', '.join(act_strs)}"
