"""Borrados con dependencias: misma regla en SQLite y PostgreSQL (claves foráneas)."""
from datetime import date, time

import pytest
from sqlalchemy.exc import IntegrityError

from models.attendance import AttendanceLog
from models.employee import User
from models.employee_group import EmployeeGroup
from models.processed_attendance import ProcessedAttendance
from models.shift import Shift
from services.deletions import DeleteBlocked, delete_employee, delete_shift


def _shift(session, name="Día"):
    shift = Shift(name=name, expected_in=time(8), expected_out=time(17))
    session.add(shift)
    session.commit()
    return shift


def _employee(session, identifier="000000000000001", shift=None):
    employee = User(identifier=identifier, first_name="Ana", is_active=True, shift_id=shift.id if shift else None)
    session.add(employee)
    session.commit()
    return employee


def test_foreign_keys_are_enforced_like_postgresql(test_db):
    """SQLite deja huérfanos si no se activan las claves foráneas; PostgreSQL no."""
    test_db.add(AttendanceLog(employee_id=999, raw_identifier="X", date=date(2026, 1, 1), time=time(8),
                              mark_type=0, flags="", source_file="t", is_processed=False))
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


def test_employee_without_history_is_deleted(test_db):
    employee = _employee(test_db)
    delete_employee(test_db, employee)
    assert test_db.query(User).count() == 0


@pytest.mark.parametrize("history", ["marks", "processed"])
def test_employee_with_history_is_kept(test_db, history):
    employee = _employee(test_db)
    if history == "marks":
        test_db.add(AttendanceLog(employee_id=employee.id, raw_identifier=employee.identifier, date=date(2026, 1, 1),
                                  time=time(8), mark_type=0, flags="", source_file="t", is_processed=False))
    else:
        test_db.add(ProcessedAttendance(employee_id=employee.id, date=date(2026, 1, 1), status="OK", total_hours=8))
    test_db.commit()

    with pytest.raises(DeleteBlocked, match="desactivalo"):
        delete_employee(test_db, employee)
    assert test_db.query(User).count() == 1


def test_unused_shift_is_deleted(test_db):
    delete_shift(test_db, _shift(test_db))
    assert test_db.query(Shift).count() == 0


@pytest.mark.parametrize("used_by", ["employee", "group"])
def test_assigned_shift_is_kept(test_db, used_by):
    shift = _shift(test_db)
    if used_by == "employee":
        _employee(test_db, shift=shift)
    else:
        test_db.add(EmployeeGroup(name="Guardia", shift_id=shift.id, is_active=True))
        test_db.commit()

    with pytest.raises(DeleteBlocked, match="Asigná otro turno"):
        delete_shift(test_db, shift)
    assert test_db.query(Shift).count() == 1
