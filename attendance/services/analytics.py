"""Read-only analytics for SRTime dashboards.

Analytics is intentionally outside the attendance engine. It reads persisted
facts, derives in-memory indicators, and never writes attendance data or
creates metric tables.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.timezone import get_timezone, local_now, local_today
from models.attendance import AttendanceLog
from models.employee import User
from models.employee_group import EmployeeGroup
from models.holiday import Holiday
from models.processed_attendance import ProcessedAttendance
from models.shift import Shift
from models.terminal import DeviceTerminal


STATUSES = ("OK", "INCOMPLETO", "AUSENTE", "PENDIENTE", "JUSTIFICADO", "FERIADO")
ACTION_STATUSES = ("INCOMPLETO", "AUSENTE", "PENDIENTE")


@dataclass(frozen=True)
class AnalyticsFilters:
    date_start: date
    date_end: date
    group_id: int | None = None
    shift_id: int | None = None
    terminal_id: int | None = None
    status: str | None = None
    employee: str | None = None
    branch: str | None = None
    sector: str | None = None
    days: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "date_start": self.date_start.isoformat(),
            "date_end": self.date_end.isoformat(),
            "group_id": self.group_id,
            "shift_id": self.shift_id,
            "terminal_id": self.terminal_id,
            "status": self.status,
            "employee": self.employee,
            "branch": self.branch,
            "sector": self.sector,
            "days": self.days,
        }


def _safe_rate(part: int | float, total: int | float) -> float:
    return round((float(part) / float(total)) * 100, 2) if total else 0.0


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value else None


def _employee_name(employee: User | None) -> str:
    if not employee:
        return "Empleado desconocido"
    return f"{employee.last_name or ''}, {employee.first_name or ''}".strip(", ") or employee.identifier


def _empty_status_counts() -> dict[str, int]:
    return {status: 0 for status in STATUSES}


def _to_dataframe(rows: list[dict[str, Any]]):
    try:
        import pandas as pd
    except Exception:
        return None
    return pd.DataFrame(rows)


def _bar_figure(title: str, labels: list[str], values: list[int | float], color: str = "#0A64AD") -> dict[str, Any]:
    """Return a Plotly-compatible figure dict without requiring Plotly in the UI."""
    try:
        import plotly.graph_objects as go

        fig = go.Figure(data=[go.Bar(x=labels, y=values, marker_color=color)])
        fig.update_layout(
            title=title,
            margin={"l": 32, "r": 12, "t": 42, "b": 40},
            height=260,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig.to_dict()
    except Exception:
        return {
            "data": [{"type": "bar", "x": labels, "y": values, "marker": {"color": color}}],
            "layout": {"title": {"text": title}, "height": 260},
        }


class AttendanceAnalytics:
    """Build dashboard metrics from persisted attendance data."""

    def __init__(self, db: Session):
        self.db = db

    def _filters(
        self,
        date_start: date | None = None,
        date_end: date | None = None,
        group_id: int | None = None,
        shift_id: int | None = None,
        terminal_id: int | None = None,
        status: str | None = None,
        employee: str | None = None,
        branch: str | None = None,
        sector: str | None = None,
        days: int | None = None,
    ) -> AnalyticsFilters:
        today = local_today()
        if days in {7, 30, 90}:
            date_end = date_end or today
            date_start = date_end - timedelta(days=days - 1)
        else:
            date_end = date_end or today
            date_start = date_start or (date_end - timedelta(days=30))
        if date_start > date_end:
            date_start, date_end = date_end, date_start
        return AnalyticsFilters(
            date_start=date_start,
            date_end=date_end,
            group_id=group_id,
            shift_id=shift_id,
            terminal_id=terminal_id,
            status=status.upper() if status else None,
            employee=employee.strip() if employee else None,
            branch=branch.strip() if branch else None,
            sector=sector.strip() if sector else None,
            days=days,
        )

    def _employees(self, filters: AnalyticsFilters) -> list[User]:
        query = self.db.query(User).filter(User.is_active.is_(True))
        if filters.group_id:
            query = query.filter(User.group_id == filters.group_id)
        if filters.shift_id:
            query = query.filter(User.shift_id == filters.shift_id)
        if filters.employee:
            needle = f"%{filters.employee}%"
            query = query.filter(
                or_(
                    User.identifier.ilike(needle),
                    User.first_name.ilike(needle),
                    User.last_name.ilike(needle),
                )
            )
        return query.all()

    def _processed(self, filters: AnalyticsFilters, employee_ids: set[int] | None = None) -> list[ProcessedAttendance]:
        query = self.db.query(ProcessedAttendance).filter(
            ProcessedAttendance.date >= filters.date_start,
            ProcessedAttendance.date <= filters.date_end,
        )
        if employee_ids is not None:
            if not employee_ids:
                return []
            query = query.filter(ProcessedAttendance.employee_id.in_(employee_ids))
        if filters.status:
            query = query.filter(ProcessedAttendance.status == filters.status)
        return query.all()

    def _raw_logs(self, filters: AnalyticsFilters, employee_ids: set[int] | None = None) -> list[AttendanceLog]:
        query = self.db.query(AttendanceLog).filter(
            AttendanceLog.date >= filters.date_start,
            AttendanceLog.date <= filters.date_end,
        )
        if employee_ids is not None:
            if not employee_ids:
                return []
            query = query.filter(or_(AttendanceLog.employee_id.in_(employee_ids), AttendanceLog.employee_id.is_(None)))
        if filters.terminal_id:
            terminal = self.db.get(DeviceTerminal, filters.terminal_id)
            if not terminal:
                return []
            query = query.filter(AttendanceLog.source_file == terminal.name)
        return query.order_by(AttendanceLog.date.desc(), AttendanceLog.time.desc()).all()

    def _context(self, filters: AnalyticsFilters) -> dict[str, Any]:
        employees = self._employees(filters)
        employee_ids = {employee.id for employee in employees}
        processed = self._processed(filters, employee_ids)
        raw_logs = self._raw_logs(filters, employee_ids)
        groups = {group.id: group for group in self.db.query(EmployeeGroup).filter(EmployeeGroup.is_active.is_(True)).all()}
        shifts = {shift.id: shift for shift in self.db.query(Shift).all()}
        terminals = self.db.query(DeviceTerminal).filter(DeviceTerminal.is_active.is_(True)).all()
        holidays = {
            item.date
            for item in self.db.query(Holiday).filter(
                Holiday.date >= filters.date_start,
                Holiday.date <= filters.date_end,
            )
        }
        return {
            "filters": filters,
            "employees": employees,
            "employee_ids": employee_ids,
            "employees_by_id": {employee.id: employee for employee in employees},
            "processed": processed,
            "raw_logs": raw_logs,
            "groups": groups,
            "shifts": shifts,
            "terminals": terminals,
            "holidays": holidays,
        }

    def _envelope(self, filters: AnalyticsFilters, data: Any, data_freshness: str = "current_read") -> dict[str, Any]:
        return {
            "filters": filters.as_dict(),
            "generated_at": local_now().isoformat(),
            "data_freshness": data_freshness,
            "data": data,
        }

    def filter_options(self) -> dict[str, Any]:
        return {
            "groups": [
                {"id": group.id, "name": group.name}
                for group in self.db.query(EmployeeGroup).filter(EmployeeGroup.is_active.is_(True)).order_by(EmployeeGroup.name).all()
            ],
            "shifts": [
                {"id": shift.id, "name": shift.name}
                for shift in self.db.query(Shift).order_by(Shift.name).all()
            ],
            "terminals": [
                {"id": terminal.id, "name": terminal.name}
                for terminal in self.db.query(DeviceTerminal).filter(DeviceTerminal.is_active.is_(True)).order_by(DeviceTerminal.name).all()
            ],
            "statuses": list(STATUSES),
            "branches": [],
            "sectors": [],
        }

    def get_overview(self, filters: AnalyticsFilters) -> dict[str, Any]:
        context = self._context(filters)
        processed: list[ProcessedAttendance] = context["processed"]
        employees: list[User] = context["employees"]
        status_counts = _empty_status_counts()
        status_counts.update(Counter(item.status or "SIN_ESTADO" for item in processed))

        expected_count = sum(1 for item in processed if item.status != "FERIADO")
        employees_without_shift = sum(1 for employee in employees if not employee.shift_id)
        terminals_with_problems = len([item for item in self.get_device_health(filters)["data"] if item["severity"] in {"alta", "media"}])
        last_processed_date = max((item.date for item in processed), default=None)

        def card(key: str, label: str, count: int, denominator: int = expected_count, severity: str = "info") -> dict[str, Any]:
            return {
                "key": key,
                "label": label,
                "count": int(count),
                "percentage": _safe_rate(count, denominator),
                "denominator": int(denominator),
                "period": {"date_start": filters.date_start.isoformat(), "date_end": filters.date_end.isoformat()},
                "data_freshness": _iso(last_processed_date) or "sin datos procesados",
                "severity": severity,
            }

        return self._envelope(
            filters,
            {
                "cards": [
                    card("expected", "Jornadas esperadas", expected_count, expected_count),
                    card("ok", "Jornadas normales", status_counts.get("OK", 0)),
                    card("incomplete", "Jornadas incompletas", status_counts.get("INCOMPLETO", 0), severity="media"),
                    card("absent", "Ausentes", status_counts.get("AUSENTE", 0), severity="alta"),
                    card("pending", "Pendientes", status_counts.get("PENDIENTE", 0), severity="media"),
                    card("justified", "Justificados", status_counts.get("JUSTIFICADO", 0)),
                    card("employees_without_shift", "Empleados sin turno", employees_without_shift, len(employees), severity="media"),
                    card("terminal_problems", "Terminales con problemas", terminals_with_problems, len(context["terminals"]), severity="media"),
                ],
                "status_counts": dict(status_counts),
                "active_employees": len(employees),
                "active_terminals": len(context["terminals"]),
                "raw_pending": sum(1 for item in context["raw_logs"] if not item.is_processed),
                "total_hours": round(sum(float(item.total_hours or 0) for item in processed), 2),
                "total_tardiness_minutes": sum(int(item.tardiness_minutes or 0) for item in processed),
                "total_overtime_minutes": sum(int(item.overtime_minutes or 0) for item in processed),
                "timezone": str(get_timezone()),
            },
        )

    def get_action_items(self, filters: AnalyticsFilters) -> dict[str, Any]:
        context = self._context(filters)
        processed: list[ProcessedAttendance] = context["processed"]
        raw_logs: list[AttendanceLog] = context["raw_logs"]
        employees: list[User] = context["employees"]
        device_health = self.get_device_health(filters)["data"]

        duplicate_keys = Counter((log.raw_identifier, log.date, log.time, log.mark_type) for log in raw_logs)
        duplicates = sum(count - 1 for count in duplicate_keys.values() if count > 1)
        unknown = sum(1 for log in raw_logs if not log.employee_id)

        items = [
            self._action("Ausencias sin resolver", "alta", sum(1 for row in processed if row.status == "AUSENTE"), "absences", {"status": "AUSENTE"}),
            self._action("Jornadas incompletas", "alta", sum(1 for row in processed if row.status == "INCOMPLETO"), "absences", {"status": "INCOMPLETO"}),
            self._action("Pendientes de revisión", "media", sum(1 for row in processed if row.status == "PENDIENTE"), "absences", {"status": "PENDIENTE"}),
            self._action("Empleados sin turno", "media", sum(1 for employee in employees if not employee.shift_id), "users", {"without_shift": "1"}),
            self._action("Marcaciones desconocidas", "media", unknown, "movements", {"unknown": "1"}),
            self._action("Marcaciones duplicadas", "baja", duplicates, "movements", {"duplicates": "1"}),
            self._action("Eventos con problemas de calidad", "media", unknown + duplicates, "movements", {"quality": "1"}),
            self._action("Terminales sin actividad reciente", "media", sum(1 for row in device_health if row["status"] != "OK"), "terminals", {"status": "inactive"}),
        ]
        return self._envelope(filters, items)

    def _action(self, label: str, severity: str, count: int, target_tab: str, drilldown: dict[str, Any]) -> dict[str, Any]:
        return {
            "label": label,
            "severity": severity,
            "count": int(count),
            "target_tab": target_tab,
            "drilldown": drilldown,
        }

    def get_status_by_group(self, filters: AnalyticsFilters) -> dict[str, Any]:
        context = self._context(filters)
        processed: list[ProcessedAttendance] = context["processed"]
        employees_by_id: dict[int, User] = context["employees_by_id"]
        groups: dict[int, EmployeeGroup] = context["groups"]
        by_group: dict[int | None, dict[str, Any]] = {}

        for group in groups.values():
            by_group[group.id] = {
                "group_id": group.id,
                "group_name": group.name,
                "expected_count": 0,
                "status_counts": _empty_status_counts(),
            }
        by_group[None] = {
            "group_id": None,
            "group_name": "Sin grupo",
            "expected_count": 0,
            "status_counts": _empty_status_counts(),
        }

        for item in processed:
            employee = employees_by_id.get(item.employee_id)
            group_id = employee.group_id if employee and employee.group_id in groups else None
            bucket = by_group[group_id]
            status = item.status or "SIN_ESTADO"
            bucket["status_counts"][status] = bucket["status_counts"].get(status, 0) + 1
            if status != "FERIADO":
                bucket["expected_count"] += 1

        rows = []
        for bucket in by_group.values():
            expected = bucket["expected_count"]
            if expected == 0 and not any(bucket["status_counts"].values()):
                continue
            rows.append({
                **bucket,
                "rates": {status: _safe_rate(bucket["status_counts"].get(status, 0), expected) for status in STATUSES},
                "drilldown": {"target_tab": "absences", "group_id": bucket["group_id"]},
            })
        return self._envelope(filters, rows)

    def get_trends(self, filters: AnalyticsFilters) -> dict[str, Any]:
        context = self._context(filters)
        rows = [
            {"date": item.date.isoformat(), "status": item.status or "SIN_ESTADO"}
            for item in context["processed"]
            if item.status != "FERIADO"
        ]
        frame = _to_dataframe(rows)
        if frame is None or frame.empty:
            return self._envelope(filters, [])

        grouped = frame.groupby(["date", "status"]).size().reset_index(name="count")
        by_day: dict[str, dict[str, int]] = defaultdict(_empty_status_counts)
        for _, row in grouped.iterrows():
            by_day[str(row["date"])][str(row["status"])] = int(row["count"])

        data = []
        for day, counts in sorted(by_day.items()):
            denominator = sum(counts.values())
            data.append({
                "date": day,
                "denominator": denominator,
                "normal_rate": _safe_rate(counts.get("OK", 0), denominator),
                "absence_rate": _safe_rate(counts.get("AUSENTE", 0), denominator),
                "incomplete_rate": _safe_rate(counts.get("INCOMPLETO", 0), denominator),
                "pending_rate": _safe_rate(counts.get("PENDIENTE", 0), denominator),
                "counts": counts,
            })
        return self._envelope(filters, data)

    def get_heatmap(self, filters: AnalyticsFilters) -> dict[str, Any]:
        context = self._context(filters)
        employees_by_id: dict[int, User] = context["employees_by_id"]
        groups: dict[int, EmployeeGroup] = context["groups"]
        matrix: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"expected": 0, "novelties": 0})

        for item in context["processed"]:
            if item.status == "FERIADO":
                continue
            employee = employees_by_id.get(item.employee_id)
            group_name = groups[employee.group_id].name if employee and employee.group_id in groups else "Sin grupo"
            key = (group_name, item.date.isoformat())
            matrix[key]["expected"] += 1
            if item.status in ACTION_STATUSES:
                matrix[key]["novelties"] += 1

        data = [
            {
                "group": group,
                "date": day,
                "expected_count": values["expected"],
                "novelty_count": values["novelties"],
                "novelty_rate": _safe_rate(values["novelties"], values["expected"]),
            }
            for (group, day), values in sorted(matrix.items())
        ]
        return self._envelope(filters, data)

    def get_recent_activity(self, filters: AnalyticsFilters, limit: int = 25) -> dict[str, Any]:
        context = self._context(filters)
        employees_by_id: dict[int, User] = context["employees_by_id"]
        raw_logs = context["raw_logs"][:limit]
        data = [
            {
                "date": log.date.isoformat(),
                "time": log.time.strftime("%H:%M:%S") if log.time else "",
                "employee": _employee_name(employees_by_id.get(log.employee_id)),
                "employee_id": log.employee_id,
                "identifier": log.raw_identifier,
                "event_type": "Entrada" if log.mark_type == 0 else "Salida" if log.mark_type == 1 else "Desconocido",
                "terminal": log.source_file or "",
                "branch": None,
                "status": "Procesado" if log.is_processed else "Pendiente",
                "source": log.source_file or "Sin origen",
            }
            for log in raw_logs
        ]
        return self._envelope(filters, data)

    def get_data_quality(self, filters: AnalyticsFilters) -> dict[str, Any]:
        context = self._context(filters)
        raw_logs: list[AttendanceLog] = context["raw_logs"]
        duplicate_keys = Counter((log.raw_identifier, log.date, log.time, log.mark_type) for log in raw_logs)
        duplicates = sum(count - 1 for count in duplicate_keys.values() if count > 1)
        unknown = sum(1 for log in raw_logs if not log.employee_id)
        pending = sum(1 for log in raw_logs if not log.is_processed)
        processed_dates = [row.date for row in context["processed"]]
        latest_processed = max(processed_dates, default=None)
        late_events = sum(1 for log in raw_logs if latest_processed and log.date < latest_processed and not log.is_processed)

        return self._envelope(
            filters,
            {
                "unknown_events": unknown,
                "duplicate_events": duplicates,
                "pending_raw_events": pending,
                "late_events": late_events,
                "recent_import_sources": [
                    {"source": source or "Sin origen", "count": count}
                    for source, count in Counter(log.source_file for log in raw_logs).most_common(8)
                ],
                "notes": [
                    "Los duplicados rechazados por constraint de base no quedan persistidos; aquí se reportan duplicados visibles en el rango.",
                    "Sucursal y sector no están disponibles en el esquema actual.",
                ],
            },
        )

    def get_device_health(self, filters: AnalyticsFilters) -> dict[str, Any]:
        context = self._context(filters)
        raw_by_source = Counter(log.source_file for log in context["raw_logs"])
        now = local_now().replace(tzinfo=None)
        rows = []
        for terminal in context["terminals"]:
            last_sync = terminal.last_sync
            minutes_since_sync = int((now - last_sync).total_seconds() / 60) if last_sync else None
            activity_count = raw_by_source.get(terminal.name, 0)
            if not terminal.is_active:
                status, severity = "INACTIVA", "baja"
            elif last_sync is None and activity_count == 0:
                status, severity = "SIN_ACTIVIDAD", "media"
            elif minutes_since_sync is not None and minutes_since_sync > 24 * 60:
                status, severity = "SIN_COMUNICACIÓN_RECIENTE", "media"
            else:
                status, severity = "OK", "info"
            rows.append({
                "terminal_id": terminal.id,
                "name": terminal.name,
                "driver_name": terminal.driver_name,
                "status": status,
                "severity": severity,
                "last_sync": _iso(last_sync),
                "last_pull_status": terminal.last_pull_status,
                "last_pull_error": terminal.last_pull_error,
                "activity_count": activity_count,
                "minutes_since_sync": minutes_since_sync,
            })
        return self._envelope(filters, rows)

    def dashboard(
        self,
        date_start: date | None = None,
        date_end: date | None = None,
        group_id: int | None = None,
        shift_id: int | None = None,
        terminal_id: int | None = None,
        status: str | None = None,
        employee: str | None = None,
        branch: str | None = None,
        sector: str | None = None,
        days: int | None = None,
    ) -> dict[str, Any]:
        filters = self._filters(date_start, date_end, group_id, shift_id, terminal_id, status, employee, branch, sector, days)
        overview = self.get_overview(filters)
        action_items = self.get_action_items(filters)
        by_group = self.get_status_by_group(filters)
        trends = self.get_trends(filters)
        heatmap = self.get_heatmap(filters)
        recent = self.get_recent_activity(filters)
        quality = self.get_data_quality(filters)
        devices = self.get_device_health(filters)
        status_counts = overview["data"]["status_counts"]
        weekly_hours = self._hours_by_period(filters, "week")
        monthly_hours = self._hours_by_period(filters, "month")
        today = local_today()
        current_week_key = f"{today.isocalendar().year}-S{today.isocalendar().week:02d}"
        current_month_key = today.strftime("%Y-%m")

        return {
            "period": {"date_start": filters.date_start.isoformat(), "date_end": filters.date_end.isoformat(), "timezone": str(get_timezone())},
            "filters": filters.as_dict(),
            "filter_options": self.filter_options(),
            "generated_at": local_now().isoformat(),
            "data_freshness": overview["data_freshness"],
            "summary": {
                "active_employees": overview["data"]["active_employees"],
                "active_terminals": overview["data"]["active_terminals"],
                "processed_records": sum(status_counts.values()),
                "attention_records": sum(status_counts.get(status_name, 0) for status_name in ACTION_STATUSES),
                "raw_pending": overview["data"]["raw_pending"],
                "total_hours": overview["data"]["total_hours"],
                "current_week_hours": next((item["hours"] for item in weekly_hours if item["week"] == current_week_key), 0.0),
                "current_month_hours": next((item["hours"] for item in monthly_hours if item["month"] == current_month_key), 0.0),
                "total_tardiness_minutes": overview["data"]["total_tardiness_minutes"],
                "total_overtime_minutes": overview["data"]["total_overtime_minutes"],
            },
            "overview": overview["data"],
            "action_items": action_items["data"],
            "status_by_group": by_group["data"],
            "trends": trends["data"],
            "heatmap": heatmap["data"],
            "recent_activity": recent["data"],
            "data_quality": quality["data"],
            "device_health": devices["data"],
            "status_counts": status_counts,
            "daily_status": [
                {"date": row["date"], "status": status_name, "count": count}
                for row in trends["data"]
                for status_name, count in row["counts"].items()
            ],
            "weekly_hours": weekly_hours,
            "monthly_hours": monthly_hours,
            "employee_groups": [
                {
                    "id": row["group_id"],
                    "name": row["group_name"],
                    "shift_id": None,
                    "is_active": True,
                    "employee_count": 0,
                    "total_hours": 0.0,
                    "status_counts": row["status_counts"],
                }
                for row in by_group["data"]
            ],
            "ungrouped_hours": 0.0,
            "figures": {
                "status_counts": _bar_figure("Jornadas por estado", list(status_counts.keys()), [status_counts[key] for key in status_counts]),
            },
        }

    def _hours_by_period(self, filters: AnalyticsFilters, period: str) -> list[dict[str, Any]]:
        context = self._context(filters)
        buckets: dict[str, float] = defaultdict(float)
        for item in context["processed"]:
            if period == "week":
                iso_year, iso_week, _ = item.date.isocalendar()
                key = f"{iso_year}-S{iso_week:02d}"
            else:
                key = item.date.strftime("%Y-%m")
            buckets[key] = round(buckets[key] + float(item.total_hours or 0), 2)
        label = "week" if period == "week" else "month"
        return [{label: key, "hours": value} for key, value in sorted(buckets.items())]
