from datetime import date, datetime, time
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from src.data.models import NotificationType, RoleCode, UpdateStatus

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: RoleCode
    name: str


class UserRead(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    is_active: bool
    role: RoleCode
    client_id: UUID | None
    client_name: str | None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    role: RoleCode
    client_id: UUID | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("full_name", "phone")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    password: str | None = Field(default=None, min_length=6, max_length=128)
    is_active: bool | None = None
    role: RoleCode | None = None
    client_id: UUID | None = None

    @field_validator("full_name", "phone")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: RoleCode
    user: UserRead


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ClientRead(BaseModel):
    id: UUID
    company_name: str
    phone: str
    email: EmailStr
    responsible_employee_id: UUID | None
    responsible_employee_name: str | None
    created_at: datetime
    updated_at: datetime


class ClientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=32)
    email: EmailStr
    responsible_employee_id: UUID | None = None

    @field_validator("company_name", "phone")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ClientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    email: EmailStr | None = None
    responsible_employee_id: UUID | None = None

    @field_validator("company_name", "phone")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()


class VersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    configuration_id: UUID
    version: str
    released_at: date | None
    is_current: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ConfigurationRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    current_version: str | None
    created_at: datetime
    updated_at: datetime


class ConfigurationDetail(ConfigurationRead):
    versions: list[VersionRead]


class ConfigurationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class ConfigurationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class VersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=64)
    released_at: date | None = None
    is_current: bool = False
    notes: str | None = None

    @field_validator("version")
    @classmethod
    def strip_version(cls, value: str) -> str:
        return value.strip()


class VersionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    released_at: date | None = None
    is_current: bool | None = None
    notes: str | None = None


class ClientConfigurationRead(BaseModel):
    id: UUID
    client_id: UUID
    company_name: str
    configuration_id: UUID
    configuration_name: str
    installed_version_id: UUID
    installed_version: str
    current_version_id: UUID | None
    current_version: str | None
    is_outdated: bool | None
    infobase_name: str | None
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ClientConfigurationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configuration_id: UUID
    installed_version_id: UUID
    infobase_name: str | None = Field(default=None, max_length=255)

    @field_validator("infobase_name")
    @classmethod
    def strip_infobase(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ClientConfigurationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    installed_version_id: UUID | None = None
    infobase_name: str | None = Field(default=None, max_length=255)

    @field_validator("infobase_name")
    @classmethod
    def strip_infobase(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class VersionCheckRead(BaseModel):
    id: UUID
    client_configuration_id: UUID
    client_id: UUID
    company_name: str
    configuration_name: str
    installed_version_id: UUID
    installed_version: str
    actual_version_id: UUID
    actual_version: str
    is_outdated: bool
    checked_at: datetime
    checked_by_id: UUID
    checked_by_name: str


class RunChecksRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: UUID | None = None
    client_configuration_id: UUID | None = None


class SkippedCheck(BaseModel):
    client_configuration_id: UUID
    reason: str


class RunChecksResponse(BaseModel):
    created: list[VersionCheckRead]
    skipped: list[SkippedCheck]


class OutdatedConfiguration(BaseModel):
    client_configuration_id: UUID
    configuration_id: UUID
    configuration_name: str
    infobase_name: str | None
    installed_version_id: UUID
    installed_version: str
    current_version_id: UUID
    current_version: str


class OutdatedClient(BaseModel):
    client_id: UUID
    company_name: str
    email: str
    phone: str
    configurations: list[OutdatedConfiguration]


class OutdatedReport(BaseModel):
    total_clients: int
    total_configurations: int
    clients: list[OutdatedClient]


class NotificationRead(BaseModel):
    id: UUID
    type: NotificationType
    title: str
    message: str
    is_read: bool
    created_at: datetime
    client_id: UUID
    company_name: str
    client_configuration_id: UUID | None
    configuration_name: str | None
    scheduled_update_id: UUID | None
    recipient_id: UUID
    created_by_id: UUID | None


class NotificationList(BaseModel):
    items: list[NotificationRead]
    total: int
    unread: int
    limit: int
    offset: int


class NotificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    client_configuration_id: UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    message: str | None = None


class SlotRead(BaseModel):
    id: UUID
    slot_date: date
    start_time: time
    end_time: time
    capacity: int
    booked: int
    remaining: int
    is_active: bool
    specialist_id: UUID
    specialist_name: str


class SlotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_date: date
    start_time: time
    end_time: time
    capacity: int = Field(default=1, ge=1, le=20)
    specialist_id: UUID | None = None

    @model_validator(mode="after")
    def check_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class SlotUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = None
    capacity: int | None = Field(default=None, ge=1, le=20)


class AvailableDate(BaseModel):
    slot_date: date
    open_slots: int
    remaining_capacity: int


class StatusEventRead(BaseModel):
    id: UUID
    old_status: UpdateStatus | None
    new_status: UpdateStatus
    comment: str | None
    changed_at: datetime
    changed_by_id: UUID
    changed_by_name: str


class ScheduledUpdateRead(BaseModel):
    id: UUID
    status: UpdateStatus
    comment: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    client_id: UUID
    company_name: str
    client_configuration_id: UUID
    configuration_name: str
    infobase_name: str | None
    source_version_id: UUID | None
    source_version: str | None
    target_version_id: UUID | None
    target_version: str | None
    slot_id: UUID | None
    slot_date: date | None
    slot_start: time | None
    slot_end: time | None
    requested_by_id: UUID
    requested_by_name: str
    assigned_specialist_id: UUID | None
    assigned_specialist_name: str | None


class ScheduledUpdateDetail(ScheduledUpdateRead):
    status_history: list[StatusEventRead]


class ScheduledUpdateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_configuration_id: UUID
    slot_id: UUID | None = None
    comment: str | None = Field(default=None, max_length=4000)


class ScheduledUpdatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: UUID | None = None
    comment: str | None = Field(default=None, max_length=4000)


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: UpdateStatus
    comment: str | None = Field(default=None, max_length=4000)


class UpdatedConfigurationReport(BaseModel):
    scheduled_update_id: UUID
    client_configuration_id: UUID
    configuration_name: str
    source_version: str | None
    target_version: str | None
    completed_at: datetime | None
    assigned_specialist_name: str | None


class UpdatedClientReport(BaseModel):
    client_id: UUID
    company_name: str
    updates: list[UpdatedConfigurationReport]


class UpdatedClientsReport(BaseModel):
    date_from: date | None
    date_to: date | None
    total_clients: int
    total_updates: int
    clients: list[UpdatedClientReport]


class UpdateBrief(BaseModel):
    id: UUID
    status: UpdateStatus
    client_id: UUID
    company_name: str
    configuration_name: str
    slot_date: date | None
    completed_at: datetime | None
    created_at: datetime


class UpdatesReport(BaseModel):
    date_from: date | None
    date_to: date | None
    planned_count: int
    completed_count: int
    cancelled_count: int
    by_status: dict[str, int]
    planned: list[UpdateBrief]
    completed: list[UpdateBrief]
