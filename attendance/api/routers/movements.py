from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user
from models.user import AuthUser
from models.attendance import AttendanceLog
from models.employee import User as EmployeeModel
from pydantic import BaseModel

router = APIRouter()

class MovementResponse(BaseModel):
    id: int
    raw_identifier: str
    employee_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date: date
    time: Optional[str] = None
    mark_type: Optional[int] = None

    class Config:
        from_attributes = True

@router.get("/", response_model=List[MovementResponse])
def read_movements(
    date_start: Optional[date] = Query(None),
    date_end: Optional[date] = Query(None),
    identifier: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    query = db.query(AttendanceLog, EmployeeModel).outerjoin(
        EmployeeModel, AttendanceLog.employee_id == EmployeeModel.id
    )

    if date_start:
        query = query.filter(AttendanceLog.date >= date_start)
    if date_end:
        query = query.filter(AttendanceLog.date <= date_end)
    if identifier:
        query = query.filter(AttendanceLog.raw_identifier == identifier)

    rows = query.order_by(AttendanceLog.date.desc(), AttendanceLog.time.desc()).offset(skip).limit(limit).all()

    results = []
    for log, emp in rows:
        results.append(MovementResponse(
            id=log.id,
            raw_identifier=log.raw_identifier,
            employee_id=log.employee_id,
            first_name=emp.first_name if emp else None,
            last_name=emp.last_name if emp else None,
            date=log.date,
            time=log.time.strftime("%H:%M:%S") if log.time else None,
            mark_type=log.mark_type,
        ))
    return results
