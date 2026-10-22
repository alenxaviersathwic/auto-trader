from typing import Any, Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.strategies.repository.registry_repository import RegistryRepository
from app.modules.strategies.schema.strategy_schema import ValidateDefinitionResponse, ValidationIssue


class DefinitionValidator:
    """Validates strategy definitions against registry items and computes executability."""

    def __init__(self, registry_repo: Optional[RegistryRepository] = None):
        self.registry_repo = registry_repo or RegistryRepository()

    async def validate(
        self,
        session: AsyncSession,
        definition: Dict[str, Any],
        format_type: str = "RULE_TREE",
    ) -> ValidateDefinitionResponse:
        issues: List[ValidationIssue] = []
        is_executable = True

        if not isinstance(definition, dict):
            return ValidateDefinitionResponse(
                valid=False,
                executable=False,
                issues=[ValidationIssue(path="definition", level="ERROR", message="Definition must be a JSON object")],
            )

        format_val = definition.get("format", format_type)

        if format_val == "SUMMARY":
            is_executable = False
            summary = definition.get("summary")
            if not summary or not isinstance(summary, dict):
                issues.append(
                    ValidationIssue(
                        path="definition.summary",
                        level="ERROR",
                        message="Format SUMMARY requires a non-empty 'summary' object",
                    )
                )
            return ValidateDefinitionResponse(
                valid=len([i for i in issues if i.level == "ERROR"]) == 0,
                executable=is_executable,
                issues=issues,
            )

        if format_val == "EVALUATOR":
            evaluator_name = definition.get("evaluator")
            if not evaluator_name:
                issues.append(
                    ValidationIssue(
                        path="definition.evaluator",
                        level="ERROR",
                        message="Format EVALUATOR requires an 'evaluator' name",
                    )
                )
                is_executable = False
            else:
                item = await self.registry_repo.get_by_type_and_code(session, "EVALUATOR", evaluator_name)
                if not item:
                    issues.append(
                        ValidationIssue(
                            path="definition.evaluator",
                            level="WARNING",
                            message=f"Evaluator '{evaluator_name}' is not in the EVALUATOR registry",
                        )
                    )
                    is_executable = False
                elif not item.executable:
                    issues.append(
                        ValidationIssue(
                            path="definition.evaluator",
                            level="WARNING",
                            message=f"Evaluator '{evaluator_name}' has no active code handler",
                        )
                    )
                    is_executable = False

            return ValidateDefinitionResponse(
                valid=len([i for i in issues if i.level == "ERROR"]) == 0,
                executable=is_executable,
                issues=issues,
            )

        # Otherwise format is RULE_TREE
        cases = definition.get("cases")
        if not cases or not isinstance(cases, list):
            issues.append(
                ValidationIssue(
                    path="definition.cases",
                    level="ERROR",
                    message="RULE_TREE format requires a non-empty 'cases' list",
                )
            )
            return ValidateDefinitionResponse(valid=False, executable=False, issues=issues)

        # Cache registry sets for fast validation
        operator_items = await self.registry_repo.get_all_by_type(session, "OPERATOR")
        valid_operators = {op.code for op in operator_items}

        indicator_items = await self.registry_repo.get_all_by_type(session, "INDICATOR")
        indicators_map = {ind.code: ind for ind in indicator_items}

        strike_items = await self.registry_repo.get_all_by_type(session, "STRIKE_SELECTOR")
        valid_strike_selectors = {st.code for st in strike_items}

        stop_items = await self.registry_repo.get_all_by_type(session, "STOP_TYPE")
        valid_stops = {st.code for st in stop_items}

        seen_leg_ids: Set[str] = set()

        for case_idx, case in enumerate(cases):
            case_path = f"definition.cases[{case_idx}]"
            if not isinstance(case, dict):
                issues.append(ValidationIssue(path=case_path, level="ERROR", message="Case must be an object"))
                continue

            # Entry validation
            entry = case.get("entry")
            if not entry or not isinstance(entry, dict):
                issues.append(ValidationIssue(path=f"{case_path}.entry", level="ERROR", message="Case missing 'entry'"))
            else:
                when_node = entry.get("when")
                if when_node:
                    exec_flag = await self._validate_condition_node(
                        node=when_node,
                        path=f"{case_path}.entry.when",
                        valid_operators=valid_operators,
                        indicators_map=indicators_map,
                        issues=issues,
                    )
                    if not exec_flag:
                        is_executable = False

                legs = entry.get("legs", [])
                if not isinstance(legs, list):
                    issues.append(ValidationIssue(path=f"{case_path}.entry.legs", level="ERROR", message="legs must be a list"))
                else:
                    for leg_idx, leg in enumerate(legs):
                        leg_path = f"{case_path}.entry.legs[{leg_idx}]"
                        leg_id = str(leg.get("legId", ""))
                        if not leg_id:
                            issues.append(ValidationIssue(path=f"{leg_path}.legId", level="ERROR", message="Missing legId"))
                        else:
                            seen_leg_ids.add(leg_id)

                        side = leg.get("side")
                        if side not in ("BUY", "SELL"):
                            issues.append(ValidationIssue(path=f"{leg_path}.side", level="ERROR", message="Side must be BUY or SELL"))

                        inst = leg.get("instrument", {})
                        strike = inst.get("strike", {})
                        selector = strike.get("selector")
                        if selector and selector not in valid_strike_selectors:
                            issues.append(
                                ValidationIssue(
                                    path=f"{leg_path}.instrument.strike.selector",
                                    level="WARNING",
                                    message=f"Strike selector '{selector}' is not recognized in registry",
                                )
                            )

                        # Stop / Target check
                        for stop_field in ("stopLoss", "target"):
                            spec = leg.get(stop_field)
                            if spec and isinstance(spec, dict):
                                stop_type = spec.get("type")
                                if stop_type and stop_type not in valid_stops:
                                    issues.append(
                                        ValidationIssue(
                                            path=f"{leg_path}.{stop_field}.type",
                                            level="WARNING",
                                            message=f"{stop_field} type '{stop_type}' not in STOP_TYPE registry",
                                        )
                                    )

            # Exit validation
            exit_block = case.get("exit")
            if exit_block and isinstance(exit_block, dict):
                when_node = exit_block.get("when")
                if when_node:
                    exec_flag = await self._validate_condition_node(
                        node=when_node,
                        path=f"{case_path}.exit.when",
                        valid_operators=valid_operators,
                        indicators_map=indicators_map,
                        issues=issues,
                    )
                    if not exec_flag:
                        is_executable = False

            # Adjustments validation
            adjustments = case.get("adjustments", [])
            for adj_idx, adj in enumerate(adjustments):
                adj_path = f"{case_path}.adjustments[{adj_idx}]"
                adj_when = adj.get("when")
                if adj_when:
                    exec_flag = await self._validate_condition_node(
                        node=adj_when,
                        path=f"{adj_path}.when",
                        valid_operators=valid_operators,
                        indicators_map=indicators_map,
                        issues=issues,
                    )
                    if not exec_flag:
                        is_executable = False

        has_errors = any(i.level == "ERROR" for i in issues)
        return ValidateDefinitionResponse(
            valid=not has_errors,
            executable=is_executable and not has_errors,
            issues=issues,
        )

    async def _validate_condition_node(
        self,
        node: Dict[str, Any],
        path: str,
        valid_operators: Set[str],
        indicators_map: Dict[str, Any],
        issues: List[ValidationIssue],
    ) -> bool:
        """Validates a condition node and returns True if fully executable."""
        if not isinstance(node, dict):
            issues.append(ValidationIssue(path=path, level="ERROR", message="Condition node must be an object"))
            return False

        # Group node
        if "op" in node:
            op = node["op"]
            if op not in ("ALL", "ANY", "NOT"):
                issues.append(ValidationIssue(path=f"{path}.op", level="ERROR", message=f"Group op must be ALL, ANY, or NOT (got '{op}')"))
                return False
            items = node.get("items", [])
            if not isinstance(items, list):
                issues.append(ValidationIssue(path=f"{path}.items", level="ERROR", message="Group items must be a list"))
                return False
            all_exec = True
            for idx, item in enumerate(items):
                item_exec = await self._validate_condition_node(
                    node=item,
                    path=f"{path}.items[{idx}]",
                    valid_operators=valid_operators,
                    indicators_map=indicators_map,
                    issues=issues,
                )
                if not item_exec:
                    all_exec = False
            return all_exec

        # Single condition: left, operator, right
        operator = node.get("operator")
        if not operator:
            issues.append(ValidationIssue(path=f"{path}.operator", level="ERROR", message="Missing condition operator"))
            return False
        if operator not in valid_operators:
            issues.append(
                ValidationIssue(
                    path=f"{path}.operator",
                    level="WARNING",
                    message=f"Operator '{operator}' not in OPERATOR registry",
                )
            )

        left_exec = self._validate_operand(node.get("left"), f"{path}.left", indicators_map, issues)
        right_exec = self._validate_operand(node.get("right"), f"{path}.right", indicators_map, issues)

        return left_exec and right_exec

    def _validate_operand(
        self,
        operand: Any,
        path: str,
        indicators_map: Dict[str, Any],
        issues: List[ValidationIssue],
    ) -> bool:
        if not operand or not isinstance(operand, dict):
            issues.append(ValidationIssue(path=path, level="ERROR", message="Operand must be a dictionary"))
            return False

        # Constant operand
        if "const" in operand:
            return True

        # Param operand
        if "param" in operand:
            return True

        source = operand.get("source")
        if not source:
            issues.append(ValidationIssue(path=f"{path}.source", level="ERROR", message="Operand missing 'source'"))
            return False

        if source == "INDICATOR":
            code = operand.get("code")
            if not code:
                issues.append(ValidationIssue(path=f"{path}.code", level="ERROR", message="INDICATOR operand missing 'code'"))
                return False
            ind_item = indicators_map.get(code)
            if not ind_item:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.code",
                        level="WARNING",
                        message=f"Indicator '{code}' not found in registry",
                    )
                )
                return False
            if not ind_item.executable:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.code",
                        level="WARNING",
                        message=f"Indicator '{code}' has no executable code handler",
                    )
                )
                return False
            return True

        return True
