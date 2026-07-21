from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import date, time

# --- USERS ---
class UserBase(BaseModel):
    identifier: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    shift_id: Optional[int] = None

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
class HolidayBase(BaseModel):
    date: date
    name: str
    is_recurring: bool = False

class HolidayCreate(HolidayBase):
    pass

class HolidayUpdate(BaseModel):
    name: Optional[str] = None
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
