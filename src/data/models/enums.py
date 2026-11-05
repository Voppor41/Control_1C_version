from enum import Enum

from sqlalchemy import Enum as SAEnum


def persisted_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    """Store enum values (``admin``) rather than member names (``ADMIN``)."""

    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda cls: [member.value for member in cls],
    )


class RoleCode(str, Enum):
    ADMIN = "admin"
    SPECIALIST = "specialist"
    MANAGER = "manager"
    CLIENT = "client"


class UpdateStatus(str, Enum):
    REQUESTED = "requested"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class NotificationType(str, Enum):
    UPDATE_AVAILABLE = "update_available"
    UPDATE_SCHEDULED = "update_scheduled"
    UPDATE_COMPLETED = "update_completed"
    UPDATE_CANCELLED = "update_cancelled"
