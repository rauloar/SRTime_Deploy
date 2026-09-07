"""Derivación de ausencias sobre la asistencia procesada.

No existe una tabla de ausencias: cada ausencia es un registro de
``processed_attendance`` sin fichadas para una jornada laboral.
"""
from datetime import date, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from models.attendance import AttendanceLog
from models.employee import User
from models.holiday import Holiday
from models.processed_attendance import ProcessedAttendance


def absence_workflow_filter():
    """Condición compartida para el ciclo de vida de una ausencia."""
    return or_(
        ProcessedAttendance.status == "AUSENTE",
        and_(ProcessedAttendance.status == "PENDIENTE", ProcessedAttendance.previous_status == "AUSENTE"),
        and_(ProcessedAttendance.status == "JUSTIFICADO", ProcessedAttendance.previous_status == "AUSENTE"),
    )


def attendance_attention_filter():
    """Casos que RR.HH. revisa en la vista de ausencias."""
    return or_(
        absence_workflow_filter(),
        ProcessedAttendance.status == "INCOMPLETO",
        ProcessedAttendance.status == "PENDIENTE",
    )


class AbsenceService:
    """Sincroniza ausencias de lunes a viernes para empleados activos con turno."""

    def __init__(self, db: Session):
        self.db = db

    def sync(self, date_start: date, date_end: date) -> int:
        employees = self.db.query(User).filter(
            User.is_active.is_(True),
            User.shift_id.isnot(None),
        ).all()
        if not employees:
            return 0

        employee_ids = [employee.id for employee in employees]
        existing = {
            (row.employee_id, row.date)
            for row in self.db.query(ProcessedAttendance).filter(
                ProcessedAttendance.employee_id.in_(employee_ids),
                ProcessedAttendance.date >= date_start,
                ProcessedAttendance.date <= date_end,
            ).all()
        }
        logged = {
            (row.employee_id, row.date)
            for row in self.db.query(AttendanceLog.employee_id, AttendanceLog.date).filter(
                AttendanceLog.employee_id.in_(employee_ids),
                AttendanceLog.date >= date_start,
                AttendanceLog.date <= date_end,
            ).distinct().all()
        }
        fixed_holidays, recurring_holidays = self._holiday_sets()

        created = 0
        day = date_start
        while day <= date_end:
            if day.weekday() < 5 and not self._is_holiday(day, fixed_holidays, recurring_holidays):
                for employee in employees:
                    key = (employee.id, day)
                    if key not in existing and key not in logged:
                        self.db.add(ProcessedAttendance(
                            employee_id=employee.id,
                            date=day,
                            total_hours=0.0,
                            tardiness_minutes=0,
                            early_departure_minutes=0,
                            overtime_minutes=0,
                            status="AUSENTE",
                        ))
                        created += 1
            day += timedelta(days=1)

        if created:
            self.db.commit()
        return created

    def justify_selected(
        self,
        record_ids: list[int],
        reason: str,
        *,
        is_root: bool,
        requested_by: str,
    ) -> dict[str, int]:
        """Justifica o solicita justificación para ausencias seleccionadas.

        El rango de fechas pertenece a la UI como filtro. La operación real se
        aplica sólo sobre registros existentes seleccionados por RR.HH. para
        evitar justificar días donde luego apareció una fichada real.
        """
        clean_ids = list(dict.fromkeys(record_ids))
        if not clean_ids:
            return {"updated": 0, "requested": 0, "skipped": 0}

        records = {
            row.id: row
            for row in self.db.query(ProcessedAttendance).filter(
                ProcessedAttendance.id.in_(clean_ids),
                absence_workflow_filter(),
            ).all()
        }

        from services.justification import JustificationService

        justification_service = JustificationService(self.db)
        updated = 0
        requested = 0
        skipped = 0

        for record_id in clean_ids:
            record = records.get(record_id)
            if not record or record.status == "JUSTIFICADO":
                skipped += 1
                continue

            if is_root:
                if record.status == "AUSENTE" or (
                    record.status == "PENDIENTE" and record.previous_status == "AUSENTE"
                ):
                    justification_service.apply_absence_direct(record, reason)
                    updated += 1
                else:
                    skipped += 1
                continue

            if record.status == "AUSENTE":
                justification_service.request_absence(record, reason, requested_by)
                requested += 1
            else:
                skipped += 1

        return {"updated": updated, "requested": requested, "skipped": skipped}

    def _holiday_sets(self) -> tuple[set[date], set[tuple[int, int]]]:
        fixed: set[date] = set()
        recurring: set[tuple[int, int]] = set()
        for holiday in self.db.query(Holiday).all():
            if holiday.is_recurring:
                recurring.add((holiday.date.month, holiday.date.day))
            else:
                fixed.add(holiday.date)
        return fixed, recurring

    @staticmethod
    def _is_holiday(day: date, fixed: set[date], recurring: set[tuple[int, int]]) -> bool:
        return day in fixed or (day.month, day.day) in recurring
