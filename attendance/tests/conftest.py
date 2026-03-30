"""
Fixtures y configuración compartida para tests.
"""
import pytest
from datetime import datetime, time, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock

from core.database import Base
from models.attendance import AttendanceLog
from models.employee import User
from models.shift import Shift
from models.processed_attendance import ProcessedAttendance


@pytest.fixture
def test_db():
    """Crea una base de datos SQLite en memoria para tests."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    engine.dispose()


@pytest.fixture
def sample_shift(test_db):
    """Crea un turno de prueba (08:00 - 17:00)."""
    shift = Shift(
        id=1,
        name="Morning Shift",
        expected_in=time(8, 0),
        expected_out=time(17, 0),
        grace_period_minutes=15,
        is_overnight_shift=False,
        break_duration_minutes=60
    )
    test_db.add(shift)
    test_db.commit()
    return shift


@pytest.fixture
def sample_overnight_shift(test_db):
    """Crea un turno nocturno de prueba (22:00 - 06:00)."""
    shift = Shift(
        id=2,
        name="Night Shift",
        expected_in=time(22, 0),
        expected_out=time(6, 0),
        grace_period_minutes=15,
        is_overnight_shift=True,
        break_duration_minutes=30
    )
    test_db.add(shift)
    test_db.commit()
    return shift


@pytest.fixture
def sample_employee(test_db, sample_shift):
    """Crea un empleado de prueba."""
    employee = User(
        id=1,
        identifier="EMP001",
        first_name="John",
        last_name="Doe",
        shift_id=sample_shift.id,
        is_active=True
    )
    test_db.add(employee)
    test_db.commit()
    return employee


@pytest.fixture
def sample_employee_night(test_db, sample_overnight_shift):
    """Crea un empleado nocturno de prueba."""
    employee = User(
        id=2,
        identifier="EMP002",
        first_name="Jane",
        last_name="Smith",
        shift_id=sample_overnight_shift.id,
        is_active=True
    )
    test_db.add(employee)
    test_db.commit()
    return employee


def create_attendance_log(
    test_db,
    employee_id: int,
    log_date: date,
    log_time: time,
    mark_type: int = 0,
    raw_identifier: str = "DEVICE001"
) -> AttendanceLog:
    """Helper para crear logs de prueba."""
    log = AttendanceLog(
        employee_id=employee_id,
        raw_identifier=raw_identifier,
        date=log_date,
        time=log_time,
        mark_type=mark_type,
        flags="",
        source_file="test",
        is_processed=False
    )
    test_db.add(log)
    test_db.commit()
    return log


@pytest.fixture
def logs_normal_day(test_db, sample_employee):
    """Crea logs para un día normal: IN a las 08:15, OUT a las 17:45."""
    today = date.today()
    
    logs = [
        create_attendance_log(test_db, sample_employee.id, today, time(8, 15), mark_type=0),
        create_attendance_log(test_db, sample_employee.id, today, time(17, 45), mark_type=1)
    ]
    return logs


@pytest.fixture
def logs_late_arrival(test_db, sample_employee):
    """Crea logs para un día con tardanza: IN a las 08:45, OUT a las 17:45."""
    today = date.today()
    
    logs = [
        create_attendance_log(test_db, sample_employee.id, today, time(8, 45), mark_type=0),
        create_attendance_log(test_db, sample_employee.id, today, time(17, 45), mark_type=1)
    ]
    return logs


@pytest.fixture
def logs_early_departure(test_db, sample_employee):
    """Crea logs para un día con salida temprana: IN a las 08:00, OUT a las 16:30."""
    today = date.today()
    
    logs = [
        create_attendance_log(test_db, sample_employee.id, today, time(8, 0), mark_type=0),
        create_attendance_log(test_db, sample_employee.id, today, time(16, 30), mark_type=1)
    ]
    return logs


@pytest.fixture
def logs_overtime(test_db, sample_employee):
    """Crea logs para un día con overtime: IN a las 08:00, OUT a las 19:00."""
    today = date.today()
    
    logs = [
        create_attendance_log(test_db, sample_employee.id, today, time(8, 0), mark_type=0),
        create_attendance_log(test_db, sample_employee.id, today, time(19, 0), mark_type=1)
    ]
    return logs


@pytest.fixture
def logs_multiple_entries(test_db, sample_employee):
    """Crea logs para un día con múltiples entradas/salidas."""
    today = date.today()
    
    logs = [
        create_attendance_log(test_db, sample_employee.id, today, time(8, 0), mark_type=0),    # IN
        create_attendance_log(test_db, sample_employee.id, today, time(12, 0), mark_type=1),   # OUT
        create_attendance_log(test_db, sample_employee.id, today, time(13, 0), mark_type=0),   # IN
        create_attendance_log(test_db, sample_employee.id, today, time(17, 0), mark_type=1)    # OUT
    ]
    return logs


@pytest.fixture
def logs_overnight(test_db, sample_employee_night):
    """Crea logs para un turno nocturno: IN a las 22:00, OUT a las 06:30 (siguiente día)."""
    today = date.today()
    
    logs = [
        create_attendance_log(test_db, sample_employee_night.id, today, time(22, 0), mark_type=0),
        create_attendance_log(test_db, sample_employee_night.id, today, time(6, 30), mark_type=1)
    ]
    return logs


@pytest.fixture
def logs_incomplete(test_db, sample_employee):
    """Crea logs para un día incompleto (solo entrada, sin salida)."""
    today = date.today()
    
    logs = [
        create_attendance_log(test_db, sample_employee.id, today, time(8, 0), mark_type=0)
    ]
    return logs
