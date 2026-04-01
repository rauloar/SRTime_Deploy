from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date, datetime

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user
from api.schemas import ProcessedAttendanceResponse
from models.processed_attendance import ProcessedAttendance
from models.employee import User as EmployeeModel
from models.shift import Shift
from models.user import AuthUser
from services.engine import AttendanceEngine

router = APIRouter()

class JustifyRequest(BaseModel):
    first_in: str   # HH:MM
    last_out: str   # HH:MM
    justification: str


@router.post("/process-pending")
def process_pending(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    engine = AttendanceEngine(db)
    count = engine.process_all(progress_callback=None, force_all=False)
    logger.info(f"Processed {count} pending days", extra={"user": current_user.username, "action": "process_pending"})
    return {"ok": True, "processed_days": count, "mode": "pending"}


@router.post("/reprocess-all")
def reprocess_all(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    engine = AttendanceEngine(db)
    count = engine.process_all(progress_callback=None, force_all=True)
    logger.info(f"Reprocessed all: {count} days", extra={"user": current_user.username, "action": "reprocess_all"})
    return {"ok": True, "processed_days": count, "mode": "all"}

@router.get("/", response_model=List[ProcessedAttendanceResponse])
def read_processed(
    date_start: Optional[date] = Query(None),
    date_end: Optional[date] = Query(None),
    employee_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    query = db.query(ProcessedAttendance)
    if date_start:
        query = query.filter(ProcessedAttendance.date >= date_start)
    if date_end:
        query = query.filter(ProcessedAttendance.date <= date_end)
    if employee_id:
        query = query.filter(ProcessedAttendance.employee_id == employee_id)
    return query.order_by(ProcessedAttendance.date.desc()).offset(skip).limit(limit).all()

@router.patch("/{record_id}/justify", response_model=ProcessedAttendanceResponse)
def justify_record(
    record_id: int,
    body: JustifyRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    rec = db.query(ProcessedAttendance).filter(ProcessedAttendance.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    if not body.justification.strip():
        raise HTTPException(status_code=400, detail="Justification text is required")

    from datetime import time as Time
    h_in, m_in = map(int, body.first_in.split(":"))
    h_out, m_out = map(int, body.last_out.split(":"))
    rec.first_in  = Time(h_in, m_in)
    rec.last_out  = Time(h_out, m_out)

    dt_in  = datetime.combine(rec.date, rec.first_in)
    dt_out = datetime.combine(rec.date, rec.last_out)
    rec.total_hours = round((dt_out - dt_in).total_seconds() / 3600.0, 2) if dt_out > dt_in else 0.0

    # Recalculate early departure and overtime
    employee = db.query(EmployeeModel).filter(EmployeeModel.id == rec.employee_id).first()
    if employee and employee.shift_id:
        shift = db.query(Shift).filter(Shift.id == employee.shift_id).first()
        if shift:
            exp_out = datetime.combine(rec.date, shift.expected_out)
            if dt_out < exp_out:
                rec.early_departure_minutes = int((exp_out - dt_out).total_seconds() / 60)
                rec.overtime_minutes = 0
            elif dt_out > exp_out:
                rec.overtime_minutes = int((dt_out - exp_out).total_seconds() / 60)
                rec.early_departure_minutes = 0
            else:
                rec.early_departure_minutes = 0
                rec.overtime_minutes = 0

    rec.status        = "JUSTIFICADO"
    rec.justification = body.justification
    db.commit()
    db.refresh(rec)
    logger.info(f"Record {record_id} justified", extra={"user": current_user.username, "action": "justify", "detail": str(record_id)})
    return rec
