"""Ausencias derivadas de processed_attendance, sin tabla propia."""
from datetime import date, time

from models.holiday import Holiday
from models.processed_attendance import ProcessedAttendance
from services.absences import AbsenceService
from services.justification import JustificationService
from tests.conftest import create_attendance_log


def test_reprocess_creates_weekday_absences_for_employee_with_shift(test_db, sample_employee):
    """Lunes a viernes sin fichadas se materializan una sola vez como AUSENTE."""
    start = date(2026, 6, 1)  # lunes

    created = AbsenceService(test_db).sync(start, date(2026, 6, 5))

    assert created == 5
    assert test_db.query(ProcessedAttendance).filter_by(status="AUSENTE").count() == 5
    # El reproceso es idempotente: nunca duplica la jornada procesada.
    assert AbsenceService(test_db).sync(start, date(2026, 6, 5)) == 0


def test_reprocess_excludes_days_with_logs_holidays_and_weekends(test_db, sample_employee):
    start = date(2026, 6, 1)  # lunes
    create_attendance_log(test_db, sample_employee.id, date(2026, 6, 2), time(8, 0))
    test_db.add(Holiday(date=date(2026, 6, 4), name="Feriado de prueba"))
    test_db.commit()

    created = AbsenceService(test_db).sync(start, date(2026, 6, 7))

    assert created == 3  # lunes, miércoles y viernes
    absence_dates = {row.date for row in test_db.query(ProcessedAttendance).all()}
    assert date(2026, 6, 2) not in absence_dates
    assert date(2026, 6, 4) not in absence_dates
    assert date(2026, 6, 6) not in absence_dates
    assert date(2026, 6, 7) not in absence_dates


def test_absence_justification_keeps_absence_provenance(test_db, sample_employee):
    record = ProcessedAttendance(
        employee_id=sample_employee.id,
        date=date(2026, 6, 1),
        status="AUSENTE",
        total_hours=0.0,
        tardiness_minutes=0,
        early_departure_minutes=0,
        overtime_minutes=0,
    )
    test_db.add(record)
    test_db.commit()

    result = JustificationService(test_db).apply_absence_direct(record, "Licencia aprobada")

    assert result.status == "JUSTIFICADO"
    assert result.previous_status == "AUSENTE"
    assert result.justification == "Licencia aprobada"
    assert result.first_in is None
    assert result.last_out is None
    assert result.total_hours == 0.0


def test_absence_request_rejection_returns_to_absent(test_db, sample_employee):
    record = ProcessedAttendance(
        employee_id=sample_employee.id,
        date=date(2026, 6, 1),
        status="AUSENTE",
        total_hours=0.0,
        tardiness_minutes=0,
        early_departure_minutes=0,
        overtime_minutes=0,
    )
    test_db.add(record)
    test_db.commit()
    service = JustificationService(test_db)

    service.request_absence(record, "Solicitud de supervisor", "supervisor01")
    assert record.status == "PENDIENTE"
    assert record.previous_status == "AUSENTE"

    result = service.reject_absence(record)
    assert result.status == "AUSENTE"
    assert result.pending_justification is None
    assert result.requested_by is None


def test_attention_view_includes_incomplete_and_pending_without_treating_them_as_absences(test_db, sample_employee):
    """La UI de Ausencias ve casos de RR.HH. sin mezclar sus workflows."""
    from services.absences import absence_workflow_filter, attendance_attention_filter

    absent = ProcessedAttendance(
        employee_id=sample_employee.id, date=date(2026, 6, 1), status="AUSENTE",
        total_hours=0.0, tardiness_minutes=0, early_departure_minutes=0, overtime_minutes=0,
    )
    incomplete = ProcessedAttendance(
        employee_id=sample_employee.id, date=date(2026, 6, 2), status="INCOMPLETO",
        total_hours=0.0, tardiness_minutes=0, early_departure_minutes=0, overtime_minutes=0,
    )
    pending_correction = ProcessedAttendance(
        employee_id=sample_employee.id, date=date(2026, 6, 3), status="PENDIENTE", previous_status="INCOMPLETO",
        total_hours=0.0, tardiness_minutes=0, early_departure_minutes=0, overtime_minutes=0,
    )
    ok = ProcessedAttendance(
        employee_id=sample_employee.id, date=date(2026, 6, 4), status="OK",
        total_hours=8.0, tardiness_minutes=0, early_departure_minutes=0, overtime_minutes=0,
    )
    test_db.add_all([absent, incomplete, pending_correction, ok])
    test_db.commit()

    attention_ids = {row.id for row in test_db.query(ProcessedAttendance).filter(attendance_attention_filter()).all()}
    absence_workflow_ids = {row.id for row in test_db.query(ProcessedAttendance).filter(absence_workflow_filter()).all()}

    assert {absent.id, incomplete.id, pending_correction.id}.issubset(attention_ids)
    assert ok.id not in attention_ids
    assert absent.id in absence_workflow_ids
    assert pending_correction.id not in absence_workflow_ids
