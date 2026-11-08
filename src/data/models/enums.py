"""Коды ролей, статусы заявки и типы уведомлений. В базу пишется значение, а не имя константы."""

from enum import Enum

from sqlalchemy import Enum as SAEnum


def persisted_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    """Колонка-строка для str-перечисления.

    Параметры:
        enum_cls: класс перечисления.
        name: имя типа в метаданных, не тип PostgreSQL.

    Возвращает:
        Тип SQLAlchemy, который пишет значение (admin), а не имя (ADMIN).
    """

    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda cls: [member.value for member in cls],
    )


class RoleCode(str, Enum):
    """Код доступа в API.

    admin, specialist и manager — должности сотрудников, они лежат в roles.
    client — пользователь компании. Такой строки в roles нет: человек хранится в client_users.
    """

    ADMIN = "admin"
    SPECIALIST = "specialist"
    MANAGER = "manager"
    CLIENT = "client"


class UpdateStatus(str, Enum):
    """Жизненный цикл заявки от запроса до выполнения или отмены."""
    REQUESTED = "requested"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class NotificationType(str, Enum):
    """О чём письмо в ленте клиента: доступно обновление, назначена дата, выполнено, отменено."""
    UPDATE_AVAILABLE = "update_available"
    UPDATE_SCHEDULED = "update_scheduled"
    UPDATE_COMPLETED = "update_completed"
    UPDATE_CANCELLED = "update_cancelled"
