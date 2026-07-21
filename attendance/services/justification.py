from datetime import time as Time

from sqlalchemy.orm import Session

from models.processed_attendance import ProcessedAttendance
from models.employee import User as EmployeeModel
from models.shift import Shift
from services.metrics import MetricsCalculator


class JustificationService:
    """
    Flujo completo de justificación de asistencia.

    Centraliza la lógica de:
    - Justificación directa (root)
    - Solicitud de justificación (supervisor)
    - Aprobación / Rechazo (root)
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Root: justificar directamente ──────────────────────────────

    def apply_direct(
        self,
        record: ProcessedAttendance,
        first_in: Time,
        last_out: Time,
        reason: str,
    ) -> ProcessedAttendance:
        record.first_in = first_in
        record.last_out = last_out

        shift = MetricsCalculator.get_shift_for_employee(self.db, record.employee_id)
        metrics = MetricsCalculator.recalculate_from_times(record.date, first_in, last_out, shift)
        record.total_hours = metrics["total_hours"]
        record.tardiness_minutes = metrics["tardiness_minutes"]
        record.early_departure_minutes = metrics["early_departure_minutes"]
        record.overtime_minutes = metrics["overtime_minutes"]

        record.status = "JUSTIFICADO"
        record.justification = reason
        self._clear_pending_fields(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    # ── Supervisor: solicitar justificación ────────────────────────

    def request(
        self,
        record: ProcessedAttendance,
        first_in: Time,
        last_out: Time,
        reason: str,
        requested_by: str,
    ) -> ProcessedAttendance:
        record.previous_status = record.status
        record.pending_first_in = first_in
        record.pending_last_out = last_out
        record.pending_justification = reason
        record.requested_by = requested_by
        record.status = "PENDIENTE"
        self.db.commit()
        self.db.refresh(record)
        return record

    # ── Root: aprobar/rechazar solicitud ──────────────────────────

    def approve(self, record: ProcessedAttendance) -> ProcessedAttendance:
        record.first_in = record.pending_first_in
        record.last_out = record.pending_last_out

        shift = MetricsCalculator.get_shift_for_employee(self.db, record.employee_id)
        if record.first_in and record.last_out:
            metrics = MetricsCalculator.recalculate_from_times(
                record.date, record.first_in, record.last_out, shift
            )
            record.total_hours = metrics["total_hours"]
            record.tardiness_minutes = metrics["tardiness_minutes"]
            record.early_departure_minutes = metrics["early_departure_minutes"]
            record.overtime_minutes = metrics["overtime_minutes"]

        record.status = "JUSTIFICADO"
        record.justification = record.pending_justification
        self._clear_pending_fields(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def reject(self, record: ProcessedAttendance) -> ProcessedAttendance:
        record.status = record.previous_status or "INCOMPLETO"
        self._clear_pending_fields(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _clear_pending_fields(record: ProcessedAttendance) -> None:
        record.pending_first_in = None
        record.pending_last_out = None
        record.pending_justification = None
        record.requested_by = None
        record.previous_status = None
