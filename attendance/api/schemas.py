from typing import Annotated, Optional, List
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from datetime import date, time

from models.holiday import NAME_MAX_LENGTH as HOLIDAY_NAME_MAX_LENGTH
from models.employee import SHIFT_ASSIGNMENT_MANUAL, SHIFT_ASSIGNMENT_SOURCES, TERMINAL_PRIVILEGES, TERMINAL_PRIVILEGE_USER

# --- USERS ---
class UserBase(BaseModel):
    identifier: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    shift_id: Optional[int] = None
    group_id: Optional[int] = None
    shift_assignment_source: str = SHIFT_ASSIGNMENT_MANUAL
    terminal_privilege: int = TERMINAL_PRIVILEGE_USER

    @field_validator("terminal_privilege")
    @classmethod
    def validate_terminal_privilege(cls, value: int) -> int:
        if value not in TERMINAL_PRIVILEGES:
            raise ValueError("terminal_privilege must be 0 (USER) or 14 (ADMIN)")
        return value

    @field_validator("shift_assignment_source")
    @classmethod
    def validate_shift_assignment_source(cls, value: str) -> str:
        normalized = (value or SHIFT_ASSIGNMENT_MANUAL).upper()
        if normalized not in SHIFT_ASSIGNMENT_SOURCES:
            raise ValueError("shift_assignment_source must be MANUAL or GROUP")
        return normalized

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- SHIFTS ---
class ShiftBase(BaseModel):
    name: str
    expected_in: time
    expected_out: time
    grace_period_minutes: int = 15
    is_overnight_shift: bool = False
    break_duration_minutes: int = 0

class ShiftResponse(ShiftBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- PROCESSED LOGS ---
class ProcessedAttendanceResponse(BaseModel):
    id: int
    employee_id: int
    date: date
    first_in: Optional[time] = None
    last_out: Optional[time] = None
    total_hours: float
    tardiness_minutes: int
    early_departure_minutes: int
    overtime_minutes: int
    status: str
    justification: Optional[str] = None
    previous_status: Optional[str] = None
    pending_first_in: Optional[time] = None
    pending_last_out: Optional[time] = None
    pending_justification: Optional[str] = None
    requested_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- HOLIDAYS ---
HolidayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=HOLIDAY_NAME_MAX_LENGTH)]
# Alias: un campo llamado ``date`` sombrea al tipo dentro de la clase.
HolidayDate = date

class HolidayBase(BaseModel):
    date: date
    name: str
    is_recurring: bool = False

class HolidayCreate(HolidayBase):
    name: HolidayName

class HolidayUpdate(BaseModel):
    date: Optional[HolidayDate] = None
    name: Optional[HolidayName] = None
    is_recurring: Optional[bool] = None

class HolidayResponse(HolidayBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- BULK IMPORT ---
class UserBulkImportRow(BaseModel):
    identifier: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    shift_id: Optional[int] = None
    group_id: Optional[int] = None
    shift_assignment_source: str = SHIFT_ASSIGNMENT_MANUAL
    terminal_privilege: int = TERMINAL_PRIVILEGE_USER

    @field_validator("terminal_privilege")
    @classmethod
    def validate_terminal_privilege(cls, value: int) -> int:
        if value not in TERMINAL_PRIVILEGES:
            raise ValueError("terminal_privilege must be 0 (USER) or 14 (ADMIN)")
        return value

class Token(BaseModel):
    access_token: str
    token_type: str
    must_change_password: bool = False


# --- AUTH USERS / ROLES ---
class AuthUserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    must_change_password: bool

    model_config = ConfigDict(from_attributes=True)


class AuthUserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"
    is_active: bool = True


class AuthUserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordChangeRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str


class AuthMeResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    must_change_password: bool


class SuggestedConnection(BaseModel):
    db_host: str
    db_port: int
    db_user: str
    db_name: str


class SetupStatusResponse(BaseModel):
    setup_required: bool
    configured: bool
    database_engine: str
    suggested_connection: SuggestedConnection


class DatabaseConnectionRequest(BaseModel):
    db_host: str = Field(min_length=1, max_length=255)
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_user: str = Field(min_length=1, max_length=128)
    db_password: str = Field(min_length=1, max_length=512)


class DatabaseSetupRequest(DatabaseConnectionRequest):
    db_name: str = Field(min_length=1, max_length=63, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")


class AdminSetupRequest(BaseModel):
    admin_password: str = Field(min_length=8, max_length=512)
    confirm_admin_password: str = Field(min_length=8, max_length=512)
