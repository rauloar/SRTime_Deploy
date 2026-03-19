from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import time as Time
from typing import Optional

from api.deps import get_db, get_current_user
from api.schemas import ShiftResponse
from models.shift import Shift
from models.user import AuthUser

router = APIRouter()

class ShiftCreate(BaseModel):
    name: str
    expected_in: str  # HH:MM
    expected_out: str  # HH:MM
    grace_period_minutes: int = 15

class ShiftUpdate(BaseModel):
    name: Optional[str] = None
    expected_in: Optional[str] = None
    expected_out: Optional[str] = None
    grace_period_minutes: Optional[int] = None

def parse_time(t: str) -> Time:
    h, m = map(int, t.split(":"))
    return Time(h, m)

@router.get("/", response_model=List[ShiftResponse])
def read_shifts(db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    return db.query(Shift).all()

@router.get("/{shift_id}", response_model=ShiftResponse)
def read_shift(shift_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift

@router.post("/", response_model=ShiftResponse)
def create_shift(data: ShiftCreate, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    shift = Shift(
        name=data.name,
        expected_in=parse_time(data.expected_in),
        expected_out=parse_time(data.expected_out),
        grace_period_minutes=data.grace_period_minutes
    )
    db.add(shift); db.commit(); db.refresh(shift)
    return shift

@router.put("/{shift_id}", response_model=ShiftResponse)
def update_shift(shift_id: int, data: ShiftUpdate, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    if data.name is not None: shift.name = data.name
    if data.expected_in is not None: shift.expected_in = parse_time(data.expected_in)
    if data.expected_out is not None: shift.expected_out = parse_time(data.expected_out)
    if data.grace_period_minutes is not None: shift.grace_period_minutes = data.grace_period_minutes
    db.commit(); db.refresh(shift)
    return shift

@router.delete("/{shift_id}")
def delete_shift(shift_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    db.delete(shift); db.commit()
    return {"ok": True, "message": f"Shift '{shift.name}' deleted"}
