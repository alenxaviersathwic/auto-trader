import math

from sqlalchemy import asc, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import ValidationException
from app.core.pagination.page_result import PageResult
from app.modules.users.entity.upstox_config_entity import UpstoxConfig
from app.modules.users.entity.user_entity import User
from app.modules.users.schema.user_schema import UserSearchFilter


class UserRepository:
    """Repository handling database operations for User and UpstoxConfig."""

    async def get_by_id(
        self,
        session: AsyncSession,
        user_id: int,
        status: EntityStatus | None = EntityStatus.ACTIVE,
    ) -> User | None:
        """Fetch user by id, optionally filtered by status."""
        stmt = select(User).options(selectinload(User.upstoxConfig)).where(User.id == user_id)
        if status is not None:
            stmt = stmt.where(User.status == status)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        session: AsyncSession,
        name: str,
        status: EntityStatus = EntityStatus.ACTIVE,
    ) -> User | None:
        """Fetch user by unique name among active accounts."""
        stmt = (
            select(User)
            .options(selectinload(User.upstoxConfig))
            .where(User.name == name, User.status == status)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_default_user(
        self,
        session: AsyncSession,
    ) -> User | None:
        """Fetch current default user."""
        stmt = (
            select(User)
            .options(selectinload(User.upstoxConfig))
            .where(User.isDefault.is_(True), User.status == EntityStatus.ACTIVE)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_auto_auth_users(
        self,
        session: AsyncSession,
    ) -> list[User]:
        """Active users whose Upstox config has auto-auth switched on."""
        stmt = (
            select(User)
            .join(UpstoxConfig, UpstoxConfig.userId == User.id)
            .options(selectinload(User.upstoxConfig))
            .where(
                User.status == EntityStatus.ACTIVE,
                UpstoxConfig.status == EntityStatus.ACTIVE,
                UpstoxConfig.autoAuthEnabled.is_(True),
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def count_active_users(
        self,
        session: AsyncSession,
    ) -> int:
        """Count total active users in system."""
        stmt = select(func.count(User.id)).where(User.status == EntityStatus.ACTIVE)
        result = await session.execute(stmt)
        return result.scalar_one() or 0

    async def search(
        self,
        session: AsyncSession,
        filter_obj: UserSearchFilter,
    ) -> PageResult[User]:
        """
        Executes paged search for users with Upstox config join,
        query searching across name, upstoxUserId, and profileName.
        """
        target_status = filter_obj.status or EntityStatus.ACTIVE

        # Base query with outer join on upstoxConfig
        base_stmt = (
            select(User)
            .options(selectinload(User.upstoxConfig))
            .outerjoin(UpstoxConfig, UpstoxConfig.userId == User.id)
            .where(User.status == target_status)
        )

        # Additional filter: authStatus
        if filter_obj.authStatus:
            base_stmt = base_stmt.where(UpstoxConfig.authStatus == filter_obj.authStatus)

        # Additional filter: isDefault
        if filter_obj.isDefault is not None:
            base_stmt = base_stmt.where(User.isDefault.is_(filter_obj.isDefault))

        # DateFilter on User.createdAt
        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                base_stmt = base_stmt.where(User.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                base_stmt = base_stmt.where(User.createdAt <= filter_obj.dateFilter.to)

        # Text query substring search across user.name, upstox.upstox_user_id, upstox.profile_name
        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            base_stmt = base_stmt.where(
                or_(
                    User.name.ilike(term),
                    UpstoxConfig.upstoxUserId.ilike(term),
                    UpstoxConfig.profileName.ilike(term),
                )
            )

        # Count total items with exact filter conditions
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_items_res = await session.execute(count_stmt)
        total_items = total_items_res.scalar_one_or_none() or 0

        # Sorting: allowed sort fields per spec: createdAt, name, tokenExpiresAt, authStatus
        sort_by = filter_obj.sortBy or "createdAt"
        sort_dir = (filter_obj.sortDir or "desc").lower()

        allowed_sorts = {"createdAt", "name", "tokenExpiresAt", "authStatus"}
        if sort_by not in allowed_sorts:
            raise ValidationException(
                message=(
                    f"Invalid sortBy field '{sort_by}'. "
                    f"Allowed fields: {sorted(list(allowed_sorts))}"
                )
            )

        if sort_by == "tokenExpiresAt":
            sort_col = UpstoxConfig.tokenExpiresAt
        elif sort_by == "authStatus":
            sort_col = UpstoxConfig.authStatus
        elif sort_by == "name":
            sort_col = User.name
        else:
            sort_col = User.createdAt

        order_clause = desc(sort_col) if sort_dir == "desc" else asc(sort_col)
        paged_stmt = base_stmt.order_by(order_clause)

        # Pagination
        offset = filter_obj.page * filter_obj.limit
        paged_stmt = paged_stmt.offset(offset).limit(filter_obj.limit)

        result = await session.execute(paged_stmt)
        users = list(result.scalars().all())

        limit = filter_obj.limit if filter_obj.limit > 0 else 10
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 0

        return PageResult(
            list=users,
            page=filter_obj.page,
            limit=limit,
            totalPages=total_pages,
            totalItems=total_items,
        )

    async def save_user(self, session: AsyncSession, user: User) -> User:
        """Add and flush user."""
        session.add(user)
        await session.flush()
        return user

    async def set_as_default(self, session: AsyncSession, user_id: int) -> None:
        """Clear isDefault for all users and set True for target user_id."""
        await session.execute(
            update(User).where(User.status == EntityStatus.ACTIVE).values(isDefault=False)
        )
        await session.execute(
            update(User)
            .where(User.id == user_id, User.status == EntityStatus.ACTIVE)
            .values(isDefault=True)
        )
        await session.flush()

    async def soft_delete(self, session: AsyncSession, user: User) -> None:
        """Soft delete user and its upstoxConfig."""
        user.status = EntityStatus.DELETED
        user.isDefault = False
        if user.upstoxConfig:
            user.upstoxConfig.status = EntityStatus.DELETED
        await session.flush()
