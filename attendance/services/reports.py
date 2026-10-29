import calendar
from datetime import date
from typing import List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from models.processed_attendance import ProcessedAttendance
from models.employee import User as EmployeeModel
from services.constants import MONTH_NAMES

# Columnas del reporte mensual: fuente única para Desktop, exportación XLSX y Web.
MONTHLY_REPORT_COLUMNS = (
    ("name", "Empleado"),
    ("total", "Días con registro"),
    ("ok", "Días OK"),
    ("incomplete", "Días incompleto"),
    ("justified", "Días justificado"),
    ("tardiness_minutes", "Min. tardanza"),
    ("overtime_minutes", "Min. horas extra"),
    ("total_hours", "Horas trabajadas"),
)


def monthly_report_headers() -> List[str]:
    return [label for _key, label in MONTHLY_REPORT_COLUMNS]


def monthly_report_rows(records: List[dict]) -> List[list]:
    return [[record[key] for key, _label in MONTHLY_REPORT_COLUMNS] for record in records]


def monthly_report_title(month_label: str, year: int) -> str:
    return f"Reporte de Asistencia — {month_label} {year}"


def monthly_report_filename(month_label: str, year: int, extension: str) -> str:
    return f"reporte_{month_label.lower()}_{year}.{extension}"


def aggregate_monthly(
    db: Session,
    year: int,
    month: int,
    employee_id: Optional[int] = None,
) -> List[dict]:
    """
    Agregación mensual de asistencia por empleado.

    Es la fuente única de verdad para el reporte mensual.
    """
    _, last_day = calendar.monthrange(year, month)
    d_start = date(year, month, 1)
    d_end = date(year, month, last_day)

    query = db.query(
        EmployeeModel.id,
        EmployeeModel.identifier,
        EmployeeModel.first_name,
        EmployeeModel.last_name,
        func.count(ProcessedAttendance.id),
        func.sum(case((ProcessedAttendance.status == "OK", 1), else_=0)),
        func.sum(case((ProcessedAttendance.status == "INCOMPLETO", 1), else_=0)),
        func.sum(case((ProcessedAttendance.status == "JUSTIFICADO", 1), else_=0)),
        func.coalesce(func.sum(ProcessedAttendance.tardiness_minutes), 0),
        func.coalesce(func.sum(ProcessedAttendance.overtime_minutes), 0),
        func.coalesce(func.sum(ProcessedAttendance.total_hours), 0.0),
    ).join(
        EmployeeModel, ProcessedAttendance.employee_id == EmployeeModel.id
    ).filter(
        ProcessedAttendance.date >= d_start,
        ProcessedAttendance.date <= d_end,
    )
    if employee_id:
        query = query.filter(EmployeeModel.id == employee_id)

    rows = query.group_by(
        EmployeeModel.id,
        EmployeeModel.identifier,
        EmployeeModel.first_name,
        EmployeeModel.last_name,
    ).all()

    result = []
    for row in rows:
        name = f"{row.last_name or ''}, {row.first_name or ''}".strip(", ") or row.identifier
        result.append({
            "employee_id": row.id,
            "identifier": row.identifier,
            "name": name,
            "total": int(row[4]),
            "ok": int(row[5]),
            "incomplete": int(row[6]),
            "justified": int(row[7]),
            "tardiness_minutes": int(row[8]),
            "overtime_minutes": int(row[9]),
            "total_hours": round(float(row[10]), 2),
        })
    return sorted(result, key=lambda item: item["name"])


def get_month_name(month: int) -> str:
    return MONTH_NAMES[month]


def build_monthly_pdf(records: List[dict], month_label: str, year: int, destination) -> None:
    """Renderiza el mismo PDF mensual para Web y Windows."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    doc = SimpleDocTemplate(
        destination,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    table_data = [[
        "Empleado", "Días\nregistro", "Días\nOK", "Días\nincompleto",
        "Días\njustificado", "Min.\ntardanza", "Min.\nhoras extra",
        "Horas\ntrabajadas",
    ]]
    table_data.extend([
        r["name"], str(r["total"]), str(r["ok"]), str(r["incomplete"]),
        str(r["justified"]), str(r["tardiness_minutes"]),
        str(r["overtime_minutes"]), f"{r['total_hours']:.2f}",
    ] for r in records)

    table = Table(
        table_data,
        colWidths=[6 * cm, 2 * cm, 2 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9D9D9")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    doc.build([
        Paragraph(monthly_report_title(month_label, year), styles["Title"]),
        Spacer(1, 0.4 * cm),
        table,
    ])
