from typing import Optional, List
from pydantic import BaseModel
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
    class Config:
        from_attributes = True

# --- SHIFTS ---
class ShiftBase(BaseModel):
    name: str
    expected_in: time
    expected_out: time
    grace_period_minutes: int = 15

class ShiftResponse(ShiftBase):
    id: int
    class Config:
        from_attributes = True

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
    
    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True


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
