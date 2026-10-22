from typing import Any, Dict, List, Set
from app.modules.strategies.schema.strategy_schema import OperandRequirement


class RequirementsExtractor:
    """Extracts all required data inputs and operands from a strategy definition."""

    def extract(self, definition: Dict[str, Any]) -> List[OperandRequirement]:
        requirements: List[OperandRequirement] = []
        seen: Set[str] = set()

        if not isinstance(definition, dict):
            return requirements

        format_val = definition.get("format", "RULE_TREE")
        if format_val == "SUMMARY":
            summary = definition.get("summary", {})
            for ind in summary.get("indicators", []):
                key = f"INDICATOR:{ind}"
                if key not in seen:
                    seen.add(key)
                    requirements.append(OperandRequirement(source="INDICATOR", code=ind))
            return requirements

        if format_val == "EVALUATOR":
            evaluator = definition.get("evaluator", "")
            requirements.append(
                OperandRequirement(
                    source="EVALUATOR",
                    code=evaluator,
                    params=definition.get("parameters"),
                )
            )
            return requirements

        # RULE_TREE
        cases = definition.get("cases", [])
        for case in cases:
            if not isinstance(case, dict):
                continue
            entry = case.get("entry", {})
            self._extract_from_node(entry.get("when"), requirements, seen)
            exit_block = case.get("exit", {})
            if isinstance(exit_block, dict):
                self._extract_from_node(exit_block.get("when"), requirements, seen)
            for adj in case.get("adjustments", []):
                self._extract_from_node(adj.get("when"), requirements, seen)

        return requirements

    def _extract_from_node(
        self,
        node: Any,
        requirements: List[OperandRequirement],
        seen: Set[str],
    ) -> None:
        if not node or not isinstance(node, dict):
            return

        if "op" in node:
            for item in node.get("items", []):
                self._extract_from_node(item, requirements, seen)
            return

        left = node.get("left")
        right = node.get("right")
        self._extract_operand(left, requirements, seen)
        self._extract_operand(right, requirements, seen)

    def _extract_operand(
        self,
        operand: Any,
        requirements: List[OperandRequirement],
        seen: Set[str],
    ) -> None:
        if not operand or not isinstance(operand, dict):
            return

        if "const" in operand or "param" in operand:
            return

        source = operand.get("source")
        if not source:
            return

        if source == "INDICATOR":
            code = operand.get("code")
            output = operand.get("output")
            key = f"INDICATOR:{code}:{output}"
            if key not in seen:
                seen.add(key)
                requirements.append(
                    OperandRequirement(
                        source="INDICATOR",
                        code=code,
                        output=output,
                        params=operand.get("params"),
                    )
                )
        elif source == "PRICE":
            field = operand.get("field")
            bar = operand.get("bar")
            timeframe = operand.get("timeframe")
            key = f"PRICE:{field}:{bar}:{timeframe}"
            if key not in seen:
                seen.add(key)
                requirements.append(
                    OperandRequirement(
                        source="PRICE",
                        field=field,
                        bar=bar,
                        timeframe=timeframe,
                    )
                )
        elif source == "DAY":
            day = operand.get("day")
            field = operand.get("field")
            key = f"DAY:{day}:{field}"
            if key not in seen:
                seen.add(key)
                requirements.append(
                    OperandRequirement(
                        source="DAY",
                        field=field,
                        bar=day,
                    )
                )
        elif source in ("TIME", "CONTEXT", "POSITION", "TRADE_PLAN"):
            field = operand.get("field")
            key = f"{source}:{field}"
            if key not in seen:
                seen.add(key)
                requirements.append(
                    OperandRequirement(
                        source=source,
                        field=field,
                    )
                )
