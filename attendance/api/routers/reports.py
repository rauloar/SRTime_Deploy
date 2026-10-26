import io
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user
from models.user import AuthUser
from services.reports import aggregate_monthly, build_monthly_pdf, get_month_name
from api.responses import streaming_excel_response
from services.export_helpers import build_excel_workbook

router = APIRouter()


@router.get("/monthly")
def monthly_summary(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    result = aggregate_monthly(db, year, month, employee_id)
    return {
        "year": year,
        "month": month,
        "month_name": get_month_name(month),
        "employees": result,
    }


@router.get("/monthly/export")
def export_monthly(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    records = aggregate_monthly(db, year, month, employee_id)
    month_label = get_month_name(month)

    headers = [
        "Empleado", "Días con registro", "Días OK",
        "Días incompleto", "Días justificado",
        "Min. tardanza", "Min. horas extra", "Horas trabajadas"
    ]
    data_rows = [
        [r["name"], r["total"], r["ok"], r["incomplete"],
         r["justified"], r["tardiness_minutes"], r["overtime_minutes"], r["total_hours"]]
        for r in records
    ]

    title = f"Reporte de Asistencia — {month_label} {year}"
    wb = build_excel_workbook(
        f"Reporte {month_label} {year}", headers, data_rows, title=title,
    )
    filename = f"reporte_{month_label.lower()}_{year}.xlsx"
    return streaming_excel_response(wb, filename)


@router.get("/monthly/export/pdf")
def export_monthly_pdf(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    records = aggregate_monthly(db, year, month, employee_id)
    month_label = get_month_name(month)

    buf = io.BytesIO()
    build_monthly_pdf(records, month_label, year, buf)
    buf.seek(0)

    filename = f"reporte_{month_label.lower()}_{year}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
