"""Regresiones cubiertas por el refactor compartido Web/Windows."""

from datetime import date, time, timedelta
from io import BytesIO

import pytest

from models.attendance import AttendanceLog
from models.processed_attendance import ProcessedAttendance
from models.terminal import DeviceTerminal
from services.addons.base_parser import AttendanceParser
from services.engine import AttendanceEngine
from services.importer_service import import_from_driver
from services.metrics import MetricsCalculator
from services.reports import build_monthly_pdf
from services.terminals import get_connection_params, merge_connection_params, public_connection_params
from tests.conftest import create_attendance_log


def test_addon_both_resolves_parser_not_driver():
    from services.addons import get_addon_info, get_parser_instance

    info = get_addon_info("ZKTeco")
    parser = get_parser_instance("ZKTeco")

    assert isinstance(parser, AttendanceParser)
    assert info["driver_class"] is not info["parser_class"]


def test_parser_only_addon_exposes_no_driver():
    """Sundial es sólo parser hasta implementar su driver directo (protocol.py)."""
    from services.addons import get_addon_info, get_parser_instance

    info = get_addon_info("Sundial ERTeckno")

    assert isinstance(get_parser_instance("Sundial ERTeckno"), AttendanceParser)
    assert info["is_driver"] is False
    assert "driver_class" not in info
    assert info["connection_fields"] == []


def test_terminal_manifests_do_not_embed_client_configuration():
    from services.addons import get_available_addons
    from services.terminals import SECRET_FIELDS

    for addon in get_available_addons().values():
        for field in addon.get("connection_fields", []):
            if field["name"] == "ip" or field["name"] in SECRET_FIELDS:
                assert field.get("default", "") == ""


def test_monthly_pdf_uses_shared_record_contract():
    output = BytesIO()
    build_monthly_pdf([{
        "name": "Pérez, Ana",
        "total": 20,
        "ok": 18,
        "incomplete": 1,
        "justified": 1,
        "tardiness_minutes": 12,
        "overtime_minutes": 30,
        "total_hours": 160.5,
    }], "Julio", 2026, output)

    assert output.getvalue().startswith(b"%PDF")


def test_terminal_public_params_never_expose_secrets():
    terminal = DeviceTerminal(
        name="Hikvision",
        driver_name="Hikvision (ISAPI)",
        connection_params={
            "ip": "10.0.0.5",
            "username": "admin",
            "password": "secret",
            "api_key": "private",
        },
    )

    assert get_connection_params(terminal)["password"] == "secret"
    assert public_connection_params(terminal) == {"ip": "10.0.0.5", "username": "admin"}
    terminal.connection_params = merge_connection_params(terminal, {"password": "new-secret"})
    assert terminal.connection_params["password"].startswith("enc:")
    assert get_connection_params(terminal)["password"] == "new-secret"


def test_single_punch_creates_incomplete_record(test_db, sample_employee):
    today = date.today()
    create_attendance_log(test_db, sample_employee.id, today, time(8, 5), mark_type=0)

    assert AttendanceEngine(test_db).process_all() == 1
    record = test_db.query(ProcessedAttendance).one()
    assert record.status == "INCOMPLETO"
    assert record.first_in == time(8, 5)
    assert record.last_out is None


def test_real_overnight_logs_are_grouped_on_start_day(
    test_db, sample_employee_night, sample_overnight_shift
):
    start = date.today() - timedelta(days=1)
    create_attendance_log(test_db, sample_employee_night.id, start, time(22, 0), mark_type=0)
    create_attendance_log(
        test_db, sample_employee_night.id, start + timedelta(days=1), time(6, 30), mark_type=1
    )

    assert AttendanceEngine(test_db).process_all() == 1
    record = test_db.query(ProcessedAttendance).one()
    assert record.date == start
    assert record.status == "OK"
    assert record.total_hours == pytest.approx(8.0)


def test_justified_overnight_metrics(sample_overnight_shift):
    metrics = MetricsCalculator.recalculate_from_times(
        date.today(), time(22, 0), time(6, 0), sample_overnight_shift
    )
    assert metrics["total_hours"] == pytest.approx(7.5)
    assert metrics["tardiness_minutes"] == 0


def test_driver_failure_is_not_reported_as_success(test_db):
    class BrokenDriver:
        display_name = "Broken"
        disconnected = False

        def connect(self, params):
            raise RuntimeError("offline")

        def disconnect(self):
            self.disconnected = True

    driver = BrokenDriver()
    with pytest.raises(RuntimeError, match="offline"):
        import_from_driver(driver, {}, test_db)
    assert driver.disconnected is True
    assert test_db.query(AttendanceLog).count() == 0
