from datetime import datetime, date, time as Time, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from core.timezone import local_datetime
from models.employee import User as EmployeeModel
from models.shift import Shift


class MetricsCalculator:
    """
    Cálculos de métricas de asistencia: horas totales, tardanza,
    retiro anticipado y horas extra.

    Es la fuente única de verdad para estas fórmulas.
    """

    @staticmethod
    def make_datetime(
        day: date,
        t: Time,
        shift: Optional[Shift] = None,
        is_expected_out: bool = False,
    ) -> datetime:
        dt = local_datetime(day, t)
        if shift and shift.is_overnight_shift and is_expected_out:
            if t < shift.expected_in:
                dt += timedelta(days=1)
        return dt

    @staticmethod
    def calculate_total_hours(
        punch_pairs: list,
        day: date,
        shift: Optional[Shift],
    ) -> float:
        total_seconds = 0.0
        for in_log, out_log in punch_pairs:
            in_dt = MetricsCalculator.make_datetime(day, in_log.time, shift)
            out_dt = MetricsCalculator.make_datetime(day, out_log.time, shift, is_expected_out=True)
            if out_dt > in_dt:
                total_seconds += (out_dt - in_dt).total_seconds()
        total_hours = total_seconds / 3600.0
        if shift and shift.break_duration_minutes:
            total_hours -= shift.break_duration_minutes / 60.0
        return max(0, total_hours)

    @staticmethod
    def calculate_metrics(
        day: date,
        first_in_time: Optional[Time],
        last_out_time: Optional[Time],
        shift: Optional[Shift],
    ) -> Tuple[int, int, int]:
        tardiness = 0
        early_departure = 0
        overtime = 0

        if not shift or not first_in_time:
            return tardiness, early_departure, overtime

        expected_in_dt = MetricsCalculator.make_datetime(day, shift.expected_in, shift)
        actual_in_dt = MetricsCalculator.make_datetime(day, first_in_time, shift)
        diff_minutes = (actual_in_dt - expected_in_dt).total_seconds() / 60.0
        if diff_minutes > shift.grace_period_minutes:
            tardiness = int(diff_minutes)

        if last_out_time:
            expected_out_dt = MetricsCalculator.make_datetime(day, shift.expected_out, shift, is_expected_out=True)
            actual_out_dt = MetricsCalculator.make_datetime(day, last_out_time, shift, is_expected_out=True)

            diff = (actual_out_dt - expected_out_dt).total_seconds() / 60.0
            if diff < 0:
                early_departure = int(-diff)
            elif diff > 0:
                overtime = int(diff)

        return tardiness, early_departure, overtime

    @staticmethod
    def recalculate_from_times(
        day: date,
        first_in: Optional[Time],
        last_out: Optional[Time],
        shift: Optional[Shift],
    ) -> dict:
        total_hours = 0.0
        tardiness = early_departure = overtime = 0

        if first_in and last_out:
            dt_in = MetricsCalculator.make_datetime(day, first_in, shift)
            dt_out = MetricsCalculator.make_datetime(day, last_out, shift, is_expected_out=True)
            if dt_out > dt_in:
                total_hours = round((dt_out - dt_in).total_seconds() / 3600.0, 2)
                if shift and shift.break_duration_minutes:
                    total_hours = max(0.0, total_hours - shift.break_duration_minutes / 60.0)

            tardiness, early_departure, overtime = MetricsCalculator.calculate_metrics(
                day, first_in, last_out, shift
            )

        return {
            "total_hours": total_hours,
            "tardiness_minutes": tardiness,
            "early_departure_minutes": early_departure,
            "overtime_minutes": overtime,
        }

    @staticmethod
    def get_shift_for_employee(db: Session, employee_id: int) -> Optional[Shift]:
        employee = db.query(EmployeeModel).filter(EmployeeModel.id == employee_id).first()
        if employee and employee.shift_id:
            return db.query(Shift).filter(Shift.id == employee.shift_id).first()
        return None
