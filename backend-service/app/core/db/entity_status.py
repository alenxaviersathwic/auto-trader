from enum import Enum


class EntityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"
