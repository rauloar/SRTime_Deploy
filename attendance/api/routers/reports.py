import io
from datetime import MAXYEAR, MINYEAR
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user
from models.user import AuthUser
from services.reports import (
    MONTHLY_REPORT_COLUMNS, aggregate_monthly, build_monthly_pdf, get_month_name,
    monthly_report_filename, monthly_report_headers, monthly_report_rows, monthly_report_title,
)
from api.responses import streaming_excel_response
from services.export_helpers import build_excel_workbook

router = APIRouter()

# El rango válido lo define el tipo date de Python, no un valor elegido a mano.
YEAR_QUERY = Query(..., ge=MINYEAR, le=MAXYEAR)
MONTH_QUERY = Query(..., ge=1, le=12)


@router.get("/monthly")
def monthly_summary(
    year: int = YEAR_QUERY,
    month: int = MONTH_QUERY,
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    result = aggregate_monthly(db, year, month, employee_id)
    return {
        "year": year,
        "month": month,
        "month_name": get_month_name(month),
        "columns": [{"key": key, "label": label} for key, label in MONTHLY_REPORT_COLUMNS],
        "employees": result,
    }


@router.get("/monthly/export")
def export_monthly(
    year: int = YEAR_QUERY,
    month: int = MONTH_QUERY,
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    records = aggregate_monthly(db, year, month, employee_id)
    month_label = get_month_name(month)

    wb = build_excel_workbook(
        f"Reporte {month_label} {year}", monthly_report_headers(), monthly_report_rows(records),
        title=monthly_report_title(month_label, year),
    )
    return streaming_excel_response(wb, monthly_report_filename(month_label, year, "xlsx"))


@router.get("/monthly/export/pdf")
def export_monthly_pdf(
    year: int = YEAR_QUERY,
    month: int = MONTH_QUERY,
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    records = aggregate_monthly(db, year, month, employee_id)
    month_label = get_month_name(month)

    buf = io.BytesIO()
    build_monthly_pdf(records, month_label, year, buf)
    buf.seek(0)

    filename = monthly_report_filename(month_label, year, "pdf")
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
