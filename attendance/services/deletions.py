"""Borrados con dependencias: misma regla en Web y Desktop, en SQLite y PostgreSQL.

PostgreSQL rechaza borrar un registro que otro referencia (clave foránea) y
SQLite, con las claves foráneas activas, hace lo mismo. En vez de un error de
base, el operador recibe un motivo y qué hacer.
"""
from __future__ import annotations

from models.attendance import AttendanceLog
from models.employee import User
from models.employee_group import EmployeeGroup
from models.processed_attendance import ProcessedAttendance
from models.shift import Shift


class DeleteBlocked(ValueError):
    """El registro tiene dependencias; el texto es para mostrarlo tal cual."""


def delete_employee(session, employee: User) -> None:
    marks = session.query(AttendanceLog).filter(AttendanceLog.employee_id == employee.id).count()
    days = session.query(ProcessedAttendance).filter(ProcessedAttendance.employee_id == employee.id).count()
    if marks or days:
        raise DeleteBlocked(
            f"El empleado {employee.identifier} tiene {marks} marcas y {days} jornadas procesadas. "
            "Eliminarlo borraría su historial: desactivalo para que deje de figurar."
        )
    session.delete(employee)
    session.commit()


def delete_shift(session, shift: Shift) -> None:
    employees = session.query(User).filter(User.shift_id == shift.id).count()
    groups = session.query(EmployeeGroup).filter(EmployeeGroup.shift_id == shift.id).count()
    if employees or groups:
        raise DeleteBlocked(
            f"El turno '{shift.name}' está asignado a {employees} empleados y {groups} grupos. "
            "Asigná otro turno antes de eliminarlo."
        )
    session.delete(shift)
    session.commit()
