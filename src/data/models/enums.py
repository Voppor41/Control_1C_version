from enum import Enum


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
