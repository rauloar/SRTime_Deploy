from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import case, func
from pydantic import BaseModel
from datetime import date, time as Time

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user, require_root, require_supervisor_or_root
from api.schemas import ProcessedAttendanceResponse
from models.processed_attendance import ProcessedAttendance
from models.user import AuthUser
from services.engine import AttendanceEngine, ProcessingAlreadyRunning
from services.justification import JustificationService
from services.metrics import MetricsCalculator
from api.responses import streaming_excel_response
from services.export_helpers import build_excel_workbook
from core.limiter import limiter
from core.database import SessionLocal
from core.operation_status import operation_status

router = APIRouter()

class JustifyRequest(BaseModel):
    first_in: str
    last_out: str
    justification: str

class RequestJustifyRequest(BaseModel):
    first_in: str
    last_out: str
    justification: str


def _run_processing_job(job_id: str, force_all: bool, username: str) -> None:
    db = SessionLocal()
    try:
        def progress(current: int, total: int) -> None:
            operation_status.update(job_id, current=current, total=total, message=f"Procesando jornada {current} de {total}")

        count = AttendanceEngine(db).process_all(progress_callback=progress, force_all=force_all)
        operation_status.complete(job_id, {"processed_days": count, "mode": "all" if force_all else "pending"}, f"Proceso completado: {count} jornadas")
        logger.info("Background attendance processing done", extra={"user": username, "action": "reprocess_all" if force_all else "process_pending"})
    except Exception as exc:
        db.rollback()
        logger.exception("Background attendance processing failed")
        operation_status.fail(job_id, f"Error al procesar: {exc}")
    finally:
        db.close()


@router.post("/jobs/{mode}", status_code=202)
def start_processing_job(
    mode: str,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    if mode not in {"pending", "all"}:
        raise HTTPException(status_code=400, detail="Unknown processing mode")
    if mode == "all" and current_user.role != "root":
        raise HTTPException(status_code=403, detail="Root role is required for historical reprocessing")
    job = operation_status.create("processing", "Procesamiento en cola")
    background_tasks.add_task(_run_processing_job, job["id"], mode == "all", current_user.username)
    return operation_status.get(job["id"])


@router.get("/jobs/{job_id}")
def get_processing_job(job_id: str, current_user: AuthUser = Depends(get_current_user)):
    job = operation_status.get(job_id)
    if not job or job["operation"] != "processing":
        raise HTTPException(status_code=404, detail="Processing job not found")
    return job


@router.post("/process-pending")
@limiter.limit("5/minute")
def process_pending(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root)
):
    engine = AttendanceEngine(db)
    try:
        count = engine.process_all(progress_callback=None, force_all=False)
    except ProcessingAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    logger.info(f"Processed {count} pending days", extra={"user": current_user.username, "action": "process_pending"})
    return {"ok": True, "processed_days": count, "mode": "pending"}


@router.post("/reprocess-all")
@limiter.limit("1/minute")
def reprocess_all(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_root)
):
    engine = AttendanceEngine(db)
    try:
        count = engine.process_all(progress_callback=None, force_all=True)
    except ProcessingAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
    current_user: AuthUser = Depends(require_root)
):
    rec = db.query(ProcessedAttendance).filter(ProcessedAttendance.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    if rec.status == "AUSENTE" or rec.previous_status == "AUSENTE":
        raise HTTPException(status_code=400, detail="Use the Absences endpoint to justify an absence")
    if not body.justification.strip():
        raise HTTPException(status_code=400, detail="Justification text is required")

    h_in, m_in = map(int, body.first_in.split(":"))
    h_out, m_out = map(int, body.last_out.split(":"))
    first_in = Time(h_in, m_in)
    last_out = Time(h_out, m_out)

    svc = JustificationService(db)
    svc.apply_direct(rec, first_in, last_out, body.justification)

    logger.info(f"Record {record_id} justified", extra={"user": current_user.username, "action": "justify", "detail": str(record_id)})
    return rec


@router.patch("/{record_id}/request-justify", response_model=ProcessedAttendanceResponse)
def request_justify(
    record_id: int,
    body: RequestJustifyRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    rec = db.query(ProcessedAttendance).filter(ProcessedAttendance.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    if rec.status == "AUSENTE" or rec.previous_status == "AUSENTE":
        raise HTTPException(status_code=400, detail="Use the Absences endpoint to justify an absence")
    if rec.status == "PENDIENTE":
        raise HTTPException(status_code=400, detail="Already has a pending justification request")
    if not body.justification.strip():
        raise HTTPException(status_code=400, detail="Justification text is required")

    h_in, m_in = map(int, body.first_in.split(":"))
    h_out, m_out = map(int, body.last_out.split(":"))

    svc = JustificationService(db)
    svc.request(rec, Time(h_in, m_in), Time(h_out, m_out),
                body.justification.strip(), current_user.username)

    logger.info(f"Record {record_id} justification requested", extra={"user": current_user.username, "action": "request_justify"})
    return rec


@router.patch("/{record_id}/approve-justify", response_model=ProcessedAttendanceResponse)
def approve_justify(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_root),
):
    rec = db.query(ProcessedAttendance).filter(ProcessedAttendance.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    if rec.previous_status == "AUSENTE":
        raise HTTPException(status_code=400, detail="Use the Absences endpoint to approve an absence justification")
    if rec.status != "PENDIENTE":
        raise HTTPException(status_code=400, detail="Record is not pending approval")

    svc = JustificationService(db)
    svc.approve(rec)

    logger.info(f"Record {record_id} justify approved", extra={"user": current_user.username, "action": "approve_justify"})
    return rec


@router.patch("/{record_id}/reject-justify", response_model=ProcessedAttendanceResponse)
def reject_justify(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_root),
):
    rec = db.query(ProcessedAttendance).filter(ProcessedAttendance.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    if rec.previous_status == "AUSENTE":
        raise HTTPException(status_code=400, detail="Use the Absences endpoint to reject an absence justification")
    if rec.status != "PENDIENTE":
        raise HTTPException(status_code=400, detail="Record is not pending approval")

    svc = JustificationService(db)
    svc.reject(rec)

    logger.info(f"Record {record_id} justify rejected", extra={"user": current_user.username, "action": "reject_justify"})
    return rec


@router.get("/summary")
def get_summary(
    date_start: Optional[date] = Query(None),
    date_end: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    query = db.query(ProcessedAttendance)
    if date_start:
        query = query.filter(ProcessedAttendance.date >= date_start)
    if date_end:
        query = query.filter(ProcessedAttendance.date <= date_end)
    totals = query.with_entities(
        func.count(ProcessedAttendance.id),
        func.coalesce(func.sum(ProcessedAttendance.tardiness_minutes), 0),
        func.coalesce(func.sum(ProcessedAttendance.overtime_minutes), 0),
        func.count(func.distinct(case(
            (ProcessedAttendance.tardiness_minutes > 0, ProcessedAttendance.employee_id)
        ))),
    ).one()
    by_status = {"OK": 0, "INCOMPLETO": 0, "JUSTIFICADO": 0}
    for status_value, count in query.with_entities(
        ProcessedAttendance.status, func.count(ProcessedAttendance.id)
    ).group_by(ProcessedAttendance.status).all():
        by_status[status_value] = count

    return {
        "period": {"start": str(date_start or ""), "end": str(date_end or "")},
        "total_records": totals[0],
        "by_status": by_status,
        "total_tardiness_minutes": totals[1],
        "total_overtime_minutes": totals[2],
        "employees_with_tardiness": totals[3],
    }


@router.get("/export")
def export_processed(
    date_start: Optional[date] = Query(None),
    date_end: Optional[date] = Query(None),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    from models.employee import User as EmployeeModel

    query = db.query(ProcessedAttendance, EmployeeModel).join(
        EmployeeModel, ProcessedAttendance.employee_id == EmployeeModel.id
    )
    if date_start:
        query = query.filter(ProcessedAttendance.date >= date_start)
    if date_end:
        query = query.filter(ProcessedAttendance.date <= date_end)
    if employee_id:
        query = query.filter(ProcessedAttendance.employee_id == employee_id)
    rows = query.order_by(ProcessedAttendance.date.desc()).all()

    headers = ["Empleado", "Fecha", "1ra Entrada", "Últ. Salida",
               "Hs Total", "Tard.(Min)", "Sal.Ant.(Min)", "HsEx.(Min)", "Estado", "Justificación"]
    data_rows = []
    for pa, emp in rows:
        name = f"{emp.last_name or ''}, {emp.first_name or ''}".strip(", ") or emp.identifier
        data_rows.append([
            name,
            str(pa.date),
            pa.first_in.strftime("%H:%M") if pa.first_in else "",
            pa.last_out.strftime("%H:%M") if pa.last_out else "",
            pa.total_hours,
            pa.tardiness_minutes,
            pa.early_departure_minutes,
            pa.overtime_minutes,
            pa.status,
            pa.justification or "",
        ])

    wb = build_excel_workbook("Asistencia Procesada", headers, data_rows)
    filename = f"asistencia_{date_start or 'all'}_{date_end or 'all'}.xlsx"
    return streaming_excel_response(wb, filename)
