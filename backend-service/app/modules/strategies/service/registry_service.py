import math
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exception.app_exceptions import ConflictException, NotFoundException, ValidationException
from app.core.pagination.page_result import PageResult
from app.modules.strategies.entity.registry_item_entity import RegistryItem
from app.modules.strategies.repository.registry_repository import RegistryRepository
from app.modules.strategies.schema.registry_schema import (
    DerivedTestRequest,
    DerivedTestResponse,
    RegistryFilter,
    RegistryItemCreate,
    RegistryItemResponse,
    RegistryItemUpdate,
)


class RegistryService:
    """Service for managing registry catalog items and evaluating derived expressions."""

    def __init__(self, registry_repo: Optional[RegistryRepository] = None):
        self.registry_repo = registry_repo or RegistryRepository()

    async def get_types(self, session: AsyncSession) -> List[str]:
        return await self.registry_repo.get_types(session)

    async def search(self, session: AsyncSession, filter_obj: RegistryFilter) -> PageResult[RegistryItemResponse]:
        page_res = await self.registry_repo.search(session, filter_obj)
        items_resp = [RegistryItemResponse.model_validate(item) for item in page_res.list]
        return PageResult(
            list=items_resp,
            page=page_res.page,
            limit=page_res.limit,
            totalPages=page_res.totalPages,
            totalItems=page_res.totalItems,
        )

    async def get_by_id(self, session: AsyncSession, item_id: int) -> RegistryItemResponse:
        item = await self.registry_repo.get_by_id(session, item_id)
        if not item:
            raise NotFoundException(message=f"Registry item with id {item_id} not found")
        return RegistryItemResponse.model_validate(item)

    async def create(self, session: AsyncSession, request: RegistryItemCreate) -> RegistryItemResponse:
        if request.kind == "BUILT_IN" and not request.handlerKey:
            raise ValidationException(message="A BUILT_IN item requires a code handler key")

        existing = await self.registry_repo.get_by_type_and_code(
            session, request.registryType, request.code
        )
        if existing:
            raise ConflictException(
                message=f"Registry item '{request.code}' already exists in registry '{request.registryType}'"
            )

        executable = bool(request.handlerKey)
        if request.kind == "DERIVED":
            executable = await self._is_derived_executable(session, request.expression)

        item = RegistryItem(
            registryType=request.registryType,
            code=request.code,
            name=request.name,
            kind=request.kind,
            version=1,
            schema=request.schema,
            expression=request.expression,
            handlerKey=request.handlerKey,
            executable=executable,
            requires=request.requires,
            description=request.description,
            enabled=request.enabled,
        )
        saved = await self.registry_repo.save(session, item)
        return RegistryItemResponse.model_validate(saved)

    async def update(self, session: AsyncSession, item_id: int, request: RegistryItemUpdate) -> RegistryItemResponse:
        item = await self.registry_repo.get_by_id(session, item_id)
        if not item:
            raise NotFoundException(message=f"Registry item with id {item_id} not found")

        if request.name is not None:
            item.name = request.name
        if request.schema is not None:
            item.schema = request.schema
        if request.handlerKey is not None:
            item.handlerKey = request.handlerKey
        if request.requires is not None:
            item.requires = request.requires
        if request.description is not None:
            item.description = request.description
        if request.enabled is not None:
            item.enabled = request.enabled

        if request.expression is not None:
            item.expression = request.expression
            if item.kind == "DERIVED":
                item.executable = await self._is_derived_executable(session, request.expression)

        item.version += 1
        saved = await self.registry_repo.save(session, item)
        return RegistryItemResponse.model_validate(saved)

    async def delete(self, session: AsyncSession, item_id: int) -> None:
        item = await self.registry_repo.get_by_id(session, item_id)
        if not item:
            raise NotFoundException(message=f"Registry item with id {item_id} not found")

        # Soft delete
        await self.registry_repo.soft_delete(session, item)

    def evaluate_derived_expression(self, expression: Dict[str, Any], context: Dict[str, Any]) -> float:
        """
        Evaluates expression grammar over operands: add, sub, mul, div, abs, min, max.
        Operand shapes:
          {"const": 10}
          {"price": "close"}
          {"ind": "EMA", "params": {"period": 20}}
          {"var": "atr"}
          {"add": [expr1, expr2]}
        """
        if not isinstance(expression, dict):
            raise ValidationException(message=f"Expression must be a dictionary, got {type(expression)}")

        # Literals & Context values
        if "const" in expression:
            return float(expression["const"])
        if "price" in expression:
            field = expression["price"]
            price_val = context.get("price", {}).get(field) or context.get(field)
            if price_val is None:
                raise ValidationException(message=f"Price field '{field}' not found in context")
            return float(price_val)
        if "var" in expression:
            var_name = expression["var"]
            val = context.get(var_name)
            if val is None:
                raise ValidationException(message=f"Variable '{var_name}' not found in context")
            return float(val)
        if "ind" in expression:
            ind_code = expression["ind"]
            # lookup indicator in context
            ind_map = context.get("indicators", {})
            val = ind_map.get(ind_code)
            if isinstance(val, dict):
                output = expression.get("output", "value")
                val = val.get(output)
            if val is None:
                raise ValidationException(message=f"Indicator value '{ind_code}' not found in context")
            return float(val)

        # Mathematical operations
        for op in ["add", "sub", "mul", "div", "min", "max"]:
            if op in expression:
                args = expression[op]
                if not isinstance(args, list) or len(args) < 2:
                    raise ValidationException(message=f"Operator '{op}' requires a list of at least 2 items")
                evaled_args = [self.evaluate_derived_expression(arg, context) for arg in args]
                if op == "add":
                    return sum(evaled_args)
                if op == "sub":
                    res = evaled_args[0]
                    for x in evaled_args[1:]:
                        res -= x
                    return res
                if op == "mul":
                    res = 1.0
                    for x in evaled_args:
                        res *= x
                    return res
                if op == "div":
                    res = evaled_args[0]
                    for x in evaled_args[1:]:
                        if abs(x) < 1e-9:
                            raise ValidationException(message="Division by zero in derived expression")
                        res /= x
                    return res
                if op == "min":
                    return min(evaled_args)
                if op == "max":
                    return max(evaled_args)

        if "abs" in expression:
            arg = expression["abs"]
            val = self.evaluate_derived_expression(arg, context)
            return abs(val)

        raise ValidationException(message=f"Unrecognized derived expression: {expression}")

    def test_derived_expression(self, request: DerivedTestRequest) -> DerivedTestResponse:
        try:
            val = self.evaluate_derived_expression(request.expression, request.context)
            return DerivedTestResponse(result=val, success=True)
        except Exception as e:
            return DerivedTestResponse(result=None, success=False, error=str(e))

    async def _is_derived_executable(self, session: AsyncSession, expression: Optional[Dict[str, Any]]) -> bool:
        if not expression:
            return False
        # Collect any referenced indicator codes
        ind_codes = self._extract_indicators_from_expr(expression)
        for code in ind_codes:
            item = await self.registry_repo.get_by_type_and_code(session, "INDICATOR", code)
            if not item or not item.executable:
                return False
        return True

    def _extract_indicators_from_expr(self, expression: Dict[str, Any]) -> List[str]:
        res = []
        if not isinstance(expression, dict):
            return res
        if "ind" in expression:
            res.append(str(expression["ind"]))
        for v in expression.values():
            if isinstance(v, dict):
                res.extend(self._extract_indicators_from_expr(v))
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        res.extend(self._extract_indicators_from_expr(item))
        return list(set(res))
