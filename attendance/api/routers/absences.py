from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db, require_root, require_supervisor_or_root
from api.schemas import ProcessedAttendanceResponse
from core.logging_config import get_logger
from models.employee import User as EmployeeModel
from models.processed_attendance import ProcessedAttendance
from models.user import AuthUser
from services.absences import AbsenceService, absence_workflow_filter, attendance_attention_filter
from services.export_helpers import build_excel_workbook, streaming_excel_response
from services.justification import JustificationService

logger = get_logger(__name__)
router = APIRouter()


class AbsenceReprocessRequest(BaseModel):
    date_start: date
    date_end: date


class AbsenceJustificationRequest(BaseModel):
    justification: str = Field(min_length=1, max_length=2000)


class BulkAbsenceJustificationRequest(BaseModel):
    record_ids: List[int] = Field(min_length=1, max_length=1000)
    justification: str = Field(min_length=1, max_length=2000)


def _get_absence_or_404(db: Session, record_id: int) -> ProcessedAttendance:
    record = db.query(ProcessedAttendance).filter(
        ProcessedAttendance.id == record_id,
        absence_workflow_filter(),
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Absence record not found")
    return record


def _attention_query(
    db: Session,
    date_start: Optional[date] = None,
    date_end: Optional[date] = None,
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
):
    query = db.query(ProcessedAttendance).filter(attendance_attention_filter())
    if date_start:
        query = query.filter(ProcessedAttendance.date >= date_start)
    if date_end:
        query = query.filter(ProcessedAttendance.date <= date_end)
    if employee_id:
        query = query.filter(ProcessedAttendance.employee_id == employee_id)
    if status:
        query = query.filter(ProcessedAttendance.status == status.upper())
    return query


def _format_time(value) -> str:
    return value.strftime("%H:%M") if value else ""


def _employee_name(employee: EmployeeModel) -> str:
    return f"{employee.last_name or ''}, {employee.first_name or ''}".strip(", ") or employee.identifier


@router.get("/", response_model=List[ProcessedAttendanceResponse])
def read_absences(
    date_start: Optional[date] = Query(None),
    date_end: Optional[date] = Query(None),
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=10000),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    query = _attention_query(db, date_start, date_end, employee_id, status)
    return query.order_by(ProcessedAttendance.date.desc(), ProcessedAttendance.employee_id).limit(limit).all()


@router.get("/export")
def export_absences(
    date_start: Optional[date] = Query(None),
    date_end: Optional[date] = Query(None),
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    query = _attention_query(db, date_start, date_end, employee_id, status).join(
        EmployeeModel,
        ProcessedAttendance.employee_id == EmployeeModel.id,
    )
    rows = query.with_entities(ProcessedAttendance, EmployeeModel).order_by(
        ProcessedAttendance.date.desc(),
        EmployeeModel.last_name,
        EmployeeModel.first_name,
    ).all()

    headers = [
        "Empleado",
        "Fecha",
        "Entrada",
        "Salida",
        "Horas",
        "Tardanza (Min)",
        "Salida Ant. (Min)",
        "Hs Extra (Min)",
        "Estado",
        "Motivo",
        "Solicitado por",
    ]
    data_rows = [
        [
            _employee_name(employee),
            str(record.date),
            _format_time(record.first_in),
            _format_time(record.last_out),
            record.total_hours,
            record.tardiness_minutes,
            record.early_departure_minutes,
            record.overtime_minutes,
            record.status,
            record.justification or record.pending_justification or "",
            record.requested_by or "",
        ]
        for record, employee in rows
    ]

    wb = build_excel_workbook("Ausencias", headers, data_rows)
    filename = f"ausencias_{date_start or 'all'}_{date_end or 'all'}.xlsx"
    return streaming_excel_response(wb, filename)


@router.post("/reprocess")
def reprocess_absences(
    body: AbsenceReprocessRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    if body.date_end < body.date_start:
        raise HTTPException(status_code=400, detail="End date must be on or after start date")
    if (body.date_end - body.date_start).days > 366:
        raise HTTPException(status_code=400, detail="The maximum reprocess range is 366 days")
    if body.date_end > date.today():
        raise HTTPException(status_code=400, detail="Absences cannot be reprocessed for future dates")

    created = AbsenceService(db).sync(body.date_start, body.date_end)
    logger.info("Absences reprocessed", extra={"user": current_user.username, "action": "reprocess_absences", "detail": str(created)})
    return {"ok": True, "created_absences": created}


@router.post("/bulk-justify")
def justify_selected_absences(
    body: BulkAbsenceJustificationRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    result = AbsenceService(db).justify_selected(
        body.record_ids,
        body.justification.strip(),
        is_root=current_user.role == "root",
        requested_by=current_user.username,
    )
    if result["updated"] == 0 and result["requested"] == 0:
        raise HTTPException(status_code=400, detail="No selectable absence records were updated")

    logger.info(
        "Selected absences justified",
        extra={
            "user": current_user.username,
            "action": "bulk_justify_absences",
            "detail": str(result),
        },
    )
    return {"ok": True, **result}


@router.patch("/{record_id}/justify", response_model=ProcessedAttendanceResponse)
def justify_absence(
    record_id: int,
    body: AbsenceJustificationRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_root),
):
    record = _get_absence_or_404(db, record_id)
    if record.status not in {"AUSENTE", "PENDIENTE"}:
        raise HTTPException(status_code=400, detail="This absence is already justified")
    JustificationService(db).apply_absence_direct(record, body.justification.strip())
    logger.info("Absence justified", extra={"user": current_user.username, "action": "justify_absence", "detail": str(record_id)})
    return record


@router.patch("/{record_id}/request-justify", response_model=ProcessedAttendanceResponse)
def request_absence_justification(
    record_id: int,
    body: AbsenceJustificationRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    record = _get_absence_or_404(db, record_id)
    if record.status != "AUSENTE":
        raise HTTPException(status_code=400, detail="Only an unhandled absence can be requested")
    JustificationService(db).request_absence(record, body.justification.strip(), current_user.username)
    logger.info("Absence justification requested", extra={"user": current_user.username, "action": "request_absence_justify", "detail": str(record_id)})
    return record


@router.patch("/{record_id}/approve-justify", response_model=ProcessedAttendanceResponse)
def approve_absence_justification(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_root),
):
    record = _get_absence_or_404(db, record_id)
    if record.status != "PENDIENTE":
        raise HTTPException(status_code=400, detail="The absence is not pending approval")
    JustificationService(db).approve_absence(record)
    logger.info("Absence justification approved", extra={"user": current_user.username, "action": "approve_absence_justify", "detail": str(record_id)})
    return record


@router.patch("/{record_id}/reject-justify", response_model=ProcessedAttendanceResponse)
def reject_absence_justification(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_root),
):
    record = _get_absence_or_404(db, record_id)
    if record.status != "PENDIENTE":
        raise HTTPException(status_code=400, detail="The absence is not pending approval")
    JustificationService(db).reject_absence(record)
    logger.info("Absence justification rejected", extra={"user": current_user.username, "action": "reject_absence_justify", "detail": str(record_id)})
    return record
