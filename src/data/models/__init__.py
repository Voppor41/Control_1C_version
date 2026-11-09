"""Реестр ORM-моделей. Импорт пакета регистрирует таблицы для Alembic."""

from .client_configurations import ClientConfiguration
from .client_users import ClientUser
from .clients import Client
from .configurations import Configuration, ConfigurationVersion
from .employees import Employee
from .enums import NotificationType, RoleCode, UpdateStatus
from .notifications import Notification
from .roles import Role
from .scheduled_updates import ScheduledUpdate, UpdateStatusHistory
from .update_slots import UpdateSlot
from .version_checks import VersionCheck

# Сотрудник или пользователь компании. Общей таблицы users больше нет.
Account = Employee | ClientUser

__all__ = [
    "Account",
    "Client",
    "ClientConfiguration",
    "ClientUser",
    "Configuration",
    "ConfigurationVersion",
    "Employee",
    "Notification",
    "NotificationType",
    "Role",
    "RoleCode",
    "ScheduledUpdate",
    "UpdateSlot",
    "UpdateStatus",
    "UpdateStatusHistory",
    "VersionCheck",
]
