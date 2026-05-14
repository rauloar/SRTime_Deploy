from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user
from api.schemas import HolidayCreate, HolidayUpdate, HolidayResponse
from models.holiday import Holiday
from models.user import AuthUser

router = APIRouter()


@router.get("/", response_model=List[HolidayResponse])
def list_holidays(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    return db.query(Holiday).order_by(Holiday.date).all()


@router.post("/", response_model=HolidayResponse, status_code=201)
def create_holiday(
    body: HolidayCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    if db.query(Holiday).filter_by(date=body.date).first():
        raise HTTPException(status_code=400, detail="A holiday already exists on that date")
    h = Holiday(date=body.date, name=body.name, is_recurring=body.is_recurring)
    db.add(h)
    db.commit()
    db.refresh(h)
    logger.info(f"Holiday created: {body.date} — {body.name}", extra={"user": current_user.username})
    return h


@router.put("/{holiday_id}", response_model=HolidayResponse)
def update_holiday(
    holiday_id: int,
    body: HolidayUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    h = db.query(Holiday).filter_by(id=holiday_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holiday not found")
    if body.name is not None:
        h.name = body.name
    if body.is_recurring is not None:
        h.is_recurring = body.is_recurring
    db.commit()
    db.refresh(h)
    return h


@router.delete("/{holiday_id}", status_code=204)
def delete_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    h = db.query(Holiday).filter_by(id=holiday_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(h)
    db.commit()
    logger.info(f"Holiday deleted: {holiday_id}", extra={"user": current_user.username})
