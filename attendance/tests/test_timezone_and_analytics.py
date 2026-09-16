from datetime import date, time

from core.timezone import clear_timezone_cache, get_timezone
from models.attendance import AttendanceLog
from models.employee import User
from models.employee_group import EmployeeGroup
from models.processed_attendance import ProcessedAttendance
from models.shift import Shift
from models.terminal import DeviceTerminal
from services.analytics import AttendanceAnalytics
from services.metrics import MetricsCalculator


def test_metrics_use_configured_business_timezone(monkeypatch, sample_shift):
    monkeypatch.setenv("TIMEZONE", "America/Argentina/Buenos_Aires")
    clear_timezone_cache()

    calculated = MetricsCalculator.make_datetime(date(2026, 7, 1), time(6, 0), sample_shift)

    assert calculated.tzinfo == get_timezone()
    assert calculated.isoformat().endswith("-03:00")


def test_analytics_dashboard_reads_current_attendance_state(test_db):
    employee = User(id=101, identifier="000000000000101", first_name="Ana", last_name="QA", is_active=True)
    test_db.add(employee)
    test_db.add_all(
        [
            ProcessedAttendance(
                employee_id=101,
                date=date(2026, 7, 1),
                first_in=time(6, 0),
                last_out=time(14, 0),
                total_hours=8,
                status="OK",
            ),
            ProcessedAttendance(
                employee_id=101,
                date=date(2026, 7, 2),
                first_in=time(6, 4),
                total_hours=0,
                status="INCOMPLETO",
                tardiness_minutes=0,
            ),
            AttendanceLog(
                employee_id=101,
                raw_identifier="000000000000101",
                date=date(2026, 7, 3),
                time=time(6, 0),
                mark_type=0,
                flags="0000000",
                source_file="test",
                is_processed=False,
            ),
        ]
    )
    test_db.commit()

    dashboard = AttendanceAnalytics(test_db).dashboard(date(2026, 7, 1), date(2026, 7, 31))

    assert dashboard["summary"]["active_employees"] == 1
    assert dashboard["summary"]["processed_records"] == 2
    assert dashboard["summary"]["raw_pending"] == 1
    assert dashboard["summary"]["attention_records"] == 1
    assert dashboard["status_counts"]["OK"] == 1
    assert dashboard["status_counts"]["INCOMPLETO"] == 1


def test_analytics_overview_uses_explicit_denominators(test_db, sample_shift):
    group = EmployeeGroup(id=1, name="Fábrica", shift_id=sample_shift.id, is_active=True)
    employee = User(id=201, identifier="000000000000201", first_name="Luis", last_name="Turno", is_active=True, shift_id=sample_shift.id, group_id=1)
    no_shift = User(id=202, identifier="000000000000202", first_name="Ana", last_name="SinTurno", is_active=True)
    test_db.add_all([group, employee, no_shift])
    test_db.add_all([
        ProcessedAttendance(employee_id=201, date=date(2026, 7, 1), status="OK", total_hours=8),
        ProcessedAttendance(employee_id=201, date=date(2026, 7, 2), status="AUSENTE", total_hours=0),
        ProcessedAttendance(employee_id=201, date=date(2026, 7, 3), status="FERIADO", total_hours=0),
    ])
    test_db.commit()

    dashboard = AttendanceAnalytics(test_db).dashboard(date(2026, 7, 1), date(2026, 7, 31))
    cards = {card["key"]: card for card in dashboard["overview"]["cards"]}

    assert dashboard["overview"]["expected_count"] == 2
    assert cards["compliance_rate"]["denominator"] == 2
    assert cards["compliance_rate"]["percentage"] == 50.0
    assert cards["unjustified_absence_rate"]["count"] == 1
    assert cards["unjustified_absence_rate"]["percentage"] == 50.0
    assert cards["avg_tardiness_per_employee"]["unit"] == "min"
    assert cards["employees_without_shift"]["count"] == 1
    assert cards["employees_without_shift"]["denominator"] == 2


def test_analytics_filters_by_group_and_keeps_attendance_read_only(test_db, sample_shift):
    other_shift = Shift(id=2, name="Administración", expected_in=time(9, 0), expected_out=time(14, 0))
    factory = EmployeeGroup(id=1, name="Fábrica", shift_id=sample_shift.id, is_active=True)
    admin = EmployeeGroup(id=2, name="Administración", shift_id=2, is_active=True)
    factory_employee = User(id=301, identifier="000000000000301", first_name="Fabián", last_name="Fábrica", is_active=True, shift_id=sample_shift.id, group_id=1)
    admin_employee = User(id=302, identifier="000000000000302", first_name="Ada", last_name="Admin", is_active=True, shift_id=2, group_id=2)
    test_db.add_all([other_shift, factory, admin, factory_employee, admin_employee])
    test_db.add_all([
        ProcessedAttendance(employee_id=301, date=date(2026, 8, 1), status="OK", total_hours=8),
        ProcessedAttendance(employee_id=302, date=date(2026, 8, 1), status="AUSENTE", total_hours=0),
        AttendanceLog(employee_id=301, raw_identifier="000000000000301", date=date(2026, 8, 1), time=time(8, 0), mark_type=0, flags="", source_file="Terminal 1", is_processed=True),
    ])
    test_db.commit()
    before_processed = test_db.query(ProcessedAttendance).count()
    before_raw = test_db.query(AttendanceLog).count()

    dashboard = AttendanceAnalytics(test_db).dashboard(date(2026, 8, 1), date(2026, 8, 31), group_id=1)

    assert dashboard["status_counts"]["OK"] == 1
    assert dashboard["status_counts"]["AUSENTE"] == 0
    assert dashboard["overview"]["active_employees"] == 1
    assert test_db.query(ProcessedAttendance).count() == before_processed
    assert test_db.query(AttendanceLog).count() == before_raw


def test_analytics_action_quality_and_device_health_from_existing_data(test_db):
    terminal = DeviceTerminal(id=1, name="Terminal 1", driver_name="ZKTeco", is_active=True)
    known = User(id=401, identifier="000000000000401", first_name="Zoé", last_name="ZK", is_active=True)
    test_db.add_all([terminal, known])
    test_db.add_all([
        ProcessedAttendance(employee_id=401, date=date(2026, 9, 1), status="INCOMPLETO", total_hours=0),
        AttendanceLog(employee_id=None, raw_identifier="000000000009999", date=date(2026, 9, 1), time=time(12, 0), mark_type=0, flags="", source_file="Terminal 1", is_processed=False),
    ])
    test_db.commit()

    service = AttendanceAnalytics(test_db)
    filters = service._filters(date(2026, 9, 1), date(2026, 9, 2))

    actions = {item["label"]: item for item in service.get_action_items(filters)["data"]}
    quality = service.get_data_quality(filters)["data"]
    devices = service.get_device_health(filters)["data"]

    assert actions["Jornadas incompletas"]["count"] == 1
    assert quality["unknown_events"] == 1
    assert devices[0]["status"] in {"SIN_ACTIVIDAD", "OK"}
