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
