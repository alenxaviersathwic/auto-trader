from typing import Optional, Union
from sqlalchemy import SmallInteger
from sqlalchemy.types import TypeDecorator
from app.core.db.entity_status import EntityStatus


class StatusType(TypeDecorator):
    """
    SQLAlchemy TypeDecorator converting between database smallint (1/0)
    and Python EntityStatus enum.
    Active = 1, Deleted = 0.
    Unknown stored values raise ValueError immediately (never default silently).
    """

    impl = SmallInteger
    cache_ok = True

    def process_bind_param(
        self,
        value: Optional[Union[EntityStatus, str, int]],
        dialect,
    ) -> Optional[int]:
        if value is None:
            return None

        if isinstance(value, EntityStatus):
            if value == EntityStatus.ACTIVE:
                return 1
            if value == EntityStatus.DELETED:
                return 0

        if isinstance(value, str):
            if value == EntityStatus.ACTIVE.value:
                return 1
            if value == EntityStatus.DELETED.value:
                return 0

        if value in (1, 0):
            return int(value)

        raise ValueError(
            f"Invalid EntityStatus value: {value}. Allowed values are EntityStatus.ACTIVE or EntityStatus.DELETED."
        )

    def process_result_value(
        self,
        value: Optional[int],
        dialect,
    ) -> Optional[EntityStatus]:
        if value is None:
            return None

        if value == 1:
            return EntityStatus.ACTIVE
        if value == 0:
            return EntityStatus.DELETED

        raise ValueError(
            f"Unknown stored status integer in database: {value}. Expected 1 (ACTIVE) or 0 (DELETED)."
        )
