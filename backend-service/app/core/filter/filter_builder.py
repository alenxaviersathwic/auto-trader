import math
from typing import Any, List, Optional, Sequence, Tuple, Type
from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.base_entity import BaseEntity
from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import ValidationException
from app.core.filter.base_filter import BaseFilter
from app.core.pagination.page_result import PageResult


class FilterBuilder:
    """
    Central FilterBuilder applying status, date range, query, sorting,
    and pagination to queries uniformly across all modules.
    """

    @classmethod
    def apply_conditions(
        cls,
        stmt: Select,
        entity_class: Type[BaseEntity],
        filter_obj: BaseFilter,
        search_fields: Optional[Sequence[str]] = None,
    ) -> Select:
        """
        Applies filter conditions:
        1. status (defaults to ACTIVE)
        2. createdAt date range
        3. query substring search across search_fields
        """
        # 1. Status filter (defaults to ACTIVE)
        target_status = filter_obj.status or EntityStatus.ACTIVE
        stmt = stmt.where(entity_class.status == target_status)

        # 2. DateFilter on createdAt
        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                stmt = stmt.where(entity_class.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                stmt = stmt.where(entity_class.createdAt <= filter_obj.dateFilter.to)

        # 3. Text query substring search (case-insensitive)
        if filter_obj.query and search_fields:
            search_pattern = f"%{filter_obj.query.strip()}%"
            conditions = []
            for field_name in search_fields:
                if hasattr(entity_class, field_name):
                    col = getattr(entity_class, field_name)
                    conditions.append(col.ilike(search_pattern))
            if conditions:
                stmt = stmt.where(or_(*conditions))

        return stmt

    @classmethod
    def apply_sort_and_paging(
        cls,
        stmt: Select,
        entity_class: Type[BaseEntity],
        filter_obj: BaseFilter,
        allowed_sort_fields: Optional[Sequence[str]] = None,
    ) -> Select:
        """
        Applies sorting and pagination:
        4. Order by sortBy and sortDir
        5. Offset and limit
        """
        sort_by = filter_obj.sortBy or "createdAt"
        sort_dir = filter_obj.sortDir or "desc"

        if allowed_sort_fields and sort_by not in allowed_sort_fields:
            raise ValidationException(
                message=f"Invalid sortBy field '{sort_by}'. Allowed fields: {list(allowed_sort_fields)}"
            )

        if not hasattr(entity_class, sort_by):
            raise ValidationException(
                message=f"Entity does not have sort field '{sort_by}'"
            )

        sort_col = getattr(entity_class, sort_by)
        order_clause = desc(sort_col).nulls_last() if sort_dir == "desc" else asc(sort_col).nulls_last()
        stmt = stmt.order_by(order_clause)

        # Pagination: zero-based page
        offset = filter_obj.page * filter_obj.limit
        stmt = stmt.offset(offset).limit(filter_obj.limit)

        return stmt

    @classmethod
    async def execute_paged_query(
        cls,
        session: AsyncSession,
        entity_class: Type[BaseEntity],
        filter_obj: BaseFilter,
        search_fields: Optional[Sequence[str]] = None,
        allowed_sort_fields: Optional[Sequence[str]] = None,
        base_query: Optional[Select] = None,
    ) -> Tuple[List[Any], int]:
        """
        Executes both item query and count query with identical conditions.
        Returns (items_list, total_items_count).
        """
        # Base select
        items_stmt = select(entity_class) if base_query is None else base_query

        # Apply conditions (status, dates, query)
        filtered_stmt = cls.apply_conditions(
            stmt=items_stmt,
            entity_class=entity_class,
            filter_obj=filter_obj,
            search_fields=search_fields,
        )

        # Build count statement from the filtered conditions
        count_stmt = select(func.count()).select_from(filtered_stmt.subquery())
        total_items_result = await session.execute(count_stmt)
        total_items = total_items_result.scalar_one_or_none() or 0

        # Apply sorting and pagination to items query
        paged_stmt = cls.apply_sort_and_paging(
            stmt=filtered_stmt,
            entity_class=entity_class,
            filter_obj=filter_obj,
            allowed_sort_fields=allowed_sort_fields,
        )

        items_result = await session.execute(paged_stmt)
        items = list(items_result.scalars().all())

        return items, total_items

    @classmethod
    def build_page_result(
        cls,
        items: List[Any],
        total_items: int,
        filter_obj: BaseFilter,
    ) -> PageResult[Any]:
        """Calculates totalPages and packages PageResult."""
        limit = filter_obj.limit if filter_obj.limit > 0 else 10
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 0
        return PageResult(
            list=items,
            page=filter_obj.page,
            limit=limit,
            totalPages=total_pages,
            totalItems=total_items,
        )

    @classmethod
    def apply(
        cls,
        stmt: Select,
        filter_obj: BaseFilter,
        model: Type[BaseEntity],
        allowed_sort_fields: Optional[Sequence[str]] = None,
        search_fields: Optional[Sequence[str]] = None,
    ) -> Tuple[Select, Select]:
        """
        Applies filtering, sorting and paging to stmt.
        Returns (paged_stmt, count_stmt).
        """
        filtered_stmt = cls.apply_conditions(stmt, model, filter_obj, search_fields)
        count_stmt = select(func.count()).select_from(filtered_stmt.subquery())
        paged_stmt = cls.apply_sort_and_paging(filtered_stmt, model, filter_obj, allowed_sort_fields)
        return paged_stmt, count_stmt

