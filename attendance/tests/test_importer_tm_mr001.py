"""Pruebas de integración para la importación nativa TM-MR001."""
from datetime import date, time
from pathlib import Path

from models.attendance import AttendanceLog
from models.employee import User
from services.addons.sundial.parser import SundialParser
from services.importer_service import import_att_logs


MOCK_FILE = Path(__file__).parent / "fixtures" / "tm_mr001_mock.txt"


def test_tm_mr001_ingests_expected_attendance_logs(test_db):
    """El archivo nativo genera logs y empleados con todos sus campos correctos."""
    nuevos, duplicados, total, _ = import_att_logs(str(MOCK_FILE), test_db)

    assert (nuevos, duplicados, total) == (6, 0, 6)
    assert test_db.query(User).count() == 3

    logs = (
        test_db.query(AttendanceLog)
        .order_by(AttendanceLog.raw_identifier, AttendanceLog.date, AttendanceLog.time)
        .all()
    )

    assert [
        (log.raw_identifier, log.date, log.time, log.mark_type, log.flags, log.is_processed)
        for log in logs
    ] == [
        ("000000000000101", date(2026, 7, 18), time(8, 0), 0, "0100100", False),
        ("000000000000101", date(2026, 7, 18), time(17, 0), 1, "0100100", False),
        ("000000000000205", date(2026, 7, 19), time(7, 45), 0, "0100100", False),
        ("000000000000205", date(2026, 7, 19), time(16, 15), 1, "0100100", False),
        ("000000000000999", date(2026, 7, 20), time(12, 0), 0, "0100100", False),
        ("000000000000999", date(2026, 7, 20), time(12, 0), 1, "0100100", False),
    ]
    assert {user.identifier for user in test_db.query(User).all()} == {
        "000000000000101",
        "000000000000205",
        "000000000000999",
    }


def test_reimporting_tm_mr001_is_deduplicated(test_db):
    """Reimportar el mismo archivo no crea logs ni empleados duplicados."""
    import_att_logs(str(MOCK_FILE), test_db)

    nuevos, duplicados, total, _ = import_att_logs(str(MOCK_FILE), test_db)

    assert (nuevos, duplicados, total) == (0, 6, 6)
    assert test_db.query(AttendanceLog).count() == 6
    assert test_db.query(User).count() == 3


def test_sundial_tm_mr001_only_uses_mark_type_for_entry_exit_state():
    """Sundial no interpreta método de verificación; sólo mark_type 0/1."""
    parser = SundialParser()

    entrada = parser.parse_line("000000000999999030926123400100100")
    salida = parser.parse_line("000000000999999030926123510100100")

    assert entrada is not None
    assert salida is not None
    assert entrada[3] == 0
    assert salida[3] == 1
    assert entrada[4] == "0100100"
    assert salida[4] == "0100100"
