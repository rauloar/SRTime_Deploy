from collections import defaultdict
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
import threading
from typing import Optional, List, Dict, Tuple

from models.attendance import AttendanceLog
from models.employee import User
from models.shift import Shift
from models.processed_attendance import ProcessedAttendance
from models.holiday import Holiday
from services.validators import AttendanceValidator, ProcessedAttendanceValidator
from services.metrics import MetricsCalculator
from services.absences import AbsenceService


logger = logging.getLogger(__name__)
_sqlite_processing_lock = threading.Lock()


class ProcessingAlreadyRunning(RuntimeError):
    pass


class AttendanceEngine:
    def __init__(self, session: Session):
        self.session = session
        self.validator = AttendanceValidator(session)
        self.pa_validator = ProcessedAttendanceValidator()
        self.processed_with_errors = []
        self._holiday_dates: set = set()
        self._recurring_holidays: set = set()
        self._load_holidays()

    def _load_holidays(self) -> None:
        for h in self.session.query(Holiday).all():
            if h.is_recurring:
                self._recurring_holidays.add((h.date.month, h.date.day))
            else:
                self._holiday_dates.add(h.date)

    def _is_holiday(self, day: date) -> bool:
        return day in self._holiday_dates or (day.month, day.day) in self._recurring_holidays

    def process_all(self, progress_callback=None, force_all=False) -> int:
        is_postgres = self.session.bind.dialect.name == "postgresql"
        acquired = False
        try:
            if is_postgres:
                acquired = bool(self.session.execute(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": 535254494545}
                ).scalar())
            else:
                acquired = _sqlite_processing_lock.acquire(blocking=False)
            if not acquired:
                raise ProcessingAlreadyRunning("Ya existe un procesamiento de asistencia en curso")
            return self._process_all(progress_callback, force_all)
        finally:
            if acquired:
                if is_postgres:
                    self.session.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": 535254494545}
                    )
                else:
                    _sqlite_processing_lock.release()

    def _process_all(self, progress_callback=None, force_all=False) -> int:
        """
        Procesa logs de asistencia sin procesar.
        
        Args:
            progress_callback: Función callback(count, total) para progress
            force_all: Si True, reprocesa TODO (incluso marcados como processed)
        
        Returns:
            Cantidad de días procesados exitosamente
        """
        try:
            # Fetch raw logs
            query = self.session.query(AttendanceLog)
            if not force_all:
                query = query.filter(AttendanceLog.is_processed == False)
                
            logs = query.order_by(
                AttendanceLog.employee_id, 
                AttendanceLog.date, 
                AttendanceLog.time
            ).all()

            if not logs:
                logger.info("No attendance logs to process")
                return 0

            # Validar logs antes de procesar. Los inválidos no entran al motor.
            validation_result = self.validator.validate_batch(logs)
            if validation_result['invalid_count'] > 0:
                logger.warning(
                    f"Found {validation_result['invalid_count']} invalid logs. "
                    f"Continuing with {validation_result['valid_count']} valid logs."
                )
            
            if validation_result['duplicate_count'] > 0:
                logger.warning(f"Found {validation_result['duplicate_count']} duplicate logs")

            valid_logs = [log for log in logs if self.validator.validate_log_entry(log)[0]]
            self.processed_with_errors.extend(
                {
                    "employee_id": item["employee_id"],
                    "date": None,
                    "error": item["error"],
                    "log_id": item["log_id"],
                }
                for item in validation_result["invalid_logs"]
            )
            employee_ids = {log.employee_id for log in valid_logs if log.employee_id}
            employees = {
                employee.id: employee
                for employee in self.session.query(User).filter(User.id.in_(employee_ids)).all()
            }
            shift_ids = {employee.shift_id for employee in employees.values() if employee.shift_id}
            shifts = {
                shift.id: shift
                for shift in self.session.query(Shift).filter(Shift.id.in_(shift_ids)).all()
            }

            # Group by (employee_id, work_date). Un OUT de un turno nocturno
            # pertenece a la jornada iniciada el día anterior.
            grouped_logs = defaultdict(list)
            overnight_start_days = {
                (log.employee_id, log.date)
                for log in valid_logs
                if (
                    (employee := employees.get(log.employee_id))
                    and (shift := shifts.get(employee.shift_id))
                    and shift.is_overnight_shift
                    and log.time >= shift.expected_in
                )
            }
            for log in valid_logs:
                employee = employees.get(log.employee_id)
                if not employee:
                    continue
                shift = shifts.get(employee.shift_id)
                work_day = log.date
                if (
                    shift
                    and shift.is_overnight_shift
                    and log.time < shift.expected_in
                    and (log.mark_type == 1 or log.time <= shift.expected_out)
                    and (log.employee_id, log.date) not in overnight_start_days
                ):
                    work_day = log.date - timedelta(days=1)
                grouped_logs[(log.employee_id, work_day)].append(log)

            existing_by_key = {}
            if grouped_logs:
                days = [key[1] for key in grouped_logs]
                existing_rows = self.session.query(ProcessedAttendance).filter(
                    ProcessedAttendance.employee_id.in_(employee_ids),
                    ProcessedAttendance.date >= min(days),
                    ProcessedAttendance.date <= max(days),
                ).all()
                existing_by_key = {
                    (row.employee_id, row.date): row for row in existing_rows
                }

            processed_count = 0
            total_days = len(grouped_logs)

            # Process each day for each employee
            for (emp_id, day), daily_logs in grouped_logs.items():
                if not daily_logs:
                    continue

                try:
                    employee = employees.get(emp_id)
                    if not employee: 
                        logger.warning(f"Employee {emp_id} not found, skipping")
                        continue
                    
                    # Check if already manually justified
                    existing = existing_by_key.get((emp_id, day))
                    
                    if existing and existing.status == "JUSTIFICADO":
                        processed_count += 1
                        if progress_callback and processed_count % 10 == 0:
                            progress_callback(processed_count, total_days)
                        continue
                    
                    shift = shifts.get(employee.shift_id)
                    
                    # Process this day
                    result = self._process_daily_logs(daily_logs, day, emp_id, employee, shift, existing)
                    
                    if result['success']:
                        processed_count += 1
                    else:
                        logger.error(f"Failed to process {emp_id} on {day}: {result['error']}")
                        self.processed_with_errors.append({
                            'employee_id': emp_id,
                            'date': day,
                            'error': result['error']
                        })
                    
                    if progress_callback and processed_count % 10 == 0:
                        progress_callback(processed_count, total_days)
                
                except Exception as e:
                    logger.error(f"Error processing {emp_id} on {day}: {str(e)}", exc_info=True)
                    self.processed_with_errors.append({
                        'employee_id': emp_id,
                        'date': day,
                        'error': str(e)
                    })
                    continue
            
            self.session.commit()

            if grouped_logs:
                days = [key[1] for key in grouped_logs]
                created_absences = AbsenceService(self.session).sync(min(days), max(days))
                if created_absences:
                    logger.info(
                        "Absence sync created %s absent days while processing attendance",
                        created_absences,
                    )

            if progress_callback:
                progress_callback(processed_count, total_days)
            logger.info(f"Processing complete: {processed_count} days processed, "
                       f"{len(self.processed_with_errors)} errors")
            return processed_count
        
        except Exception as e:
            logger.critical(f"Critical error in process_all: {str(e)}", exc_info=True)
            self.session.rollback()
            raise

    def _process_daily_logs(
        self,
        daily_logs: List[AttendanceLog],
        day: date,
        emp_id: int,
        employee: User,
        shift: Optional[Shift],
        existing: Optional[ProcessedAttendance]
    ) -> Dict:
        """
        Procesa los logs de un empleado para un día específico.
        
        Returns:
            {'success': bool, 'error': str or None}
        """
        try:
            daily_logs = sorted(daily_logs, key=lambda log: (log.date, log.time, log.id or 0))

            # Una única marcación es un resultado válido pero incompleto.
            if len(daily_logs) == 1:
                first_in_time = daily_logs[0].time
                last_out_time = None
                total_hours = 0.0
                tardiness, early_departure, overtime = MetricsCalculator.calculate_metrics(
                    day, first_in_time, None, shift
                )
                status = "FERIADO" if self._is_holiday(day) else "INCOMPLETO"
                return self._save_processed(
                    daily_logs, day, emp_id, existing, first_in_time, last_out_time,
                    total_hours, tardiness, early_departure, overtime, status,
                )

            punch_pairs = self._match_punch_pairs(daily_logs, shift)
            
            if not punch_pairs:
                return {'success': False, 'error': 'No valid punch pairs found'}
            
            # Calculate hours and metrics
            first_in_time = punch_pairs[0][0].time
            last_out_time = punch_pairs[-1][1].time
            
            total_hours = MetricsCalculator.calculate_total_hours(punch_pairs, day, shift)
            tardiness, early_departure, overtime = MetricsCalculator.calculate_metrics(
                day, first_in_time, last_out_time, shift
            )
            
            # Validate calculated values
            is_valid, error_msg = self.pa_validator.validate_calculated_hours(
                total_hours, tardiness, overtime, early_departure
            )
            if not is_valid:
                return {'success': False, 'error': f'Validation failed: {error_msg}'}

            # Determine status. Un punch sin pareja conserva la jornada como
            # incompleta aun si existieron pares válidos.
            has_unmatched = len(punch_pairs) * 2 < len(daily_logs)
            if self._is_holiday(day):
                status = "FERIADO"
                tardiness = 0
                early_departure = 0
            elif has_unmatched:
                status = "INCOMPLETO"
            else:
                status = "OK"
            
            return self._save_processed(
                daily_logs, day, emp_id, existing, first_in_time, last_out_time,
                total_hours, tardiness, early_departure, overtime, status,
            )

        except Exception as e:
            logger.error(f"Error in _process_daily_logs: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _save_processed(
        self, daily_logs, day, emp_id, existing, first_in_time, last_out_time,
        total_hours, tardiness, early_departure, overtime, status,
    ) -> Dict:
            # Upsert
            if not existing:
                existing = ProcessedAttendance(employee_id=emp_id, date=day)
                self.session.add(existing)
            
            existing.first_in = first_in_time
            existing.last_out = last_out_time
            existing.total_hours = round(total_hours, 2)
            existing.tardiness_minutes = tardiness
            existing.early_departure_minutes = early_departure
            existing.overtime_minutes = overtime
            existing.status = status
            
            # Mark raw logs as processed
            for log in daily_logs:
                log.is_processed = True
            
            return {'success': True, 'error': None}

    def _match_punch_pairs(self, daily_logs: List[AttendanceLog], shift: Optional[Shift] = None) -> List[Tuple[AttendanceLog, AttendanceLog]]:
        """
        Empareja punches IN/OUT inteligentemente.
        
        Estrategia:
        1. Si existe mark_type, usarlo para diferenciar IN vs OUT
        2. Si no, asumir patrón alternado: IN, OUT, IN, OUT...
        3. Si número impar de punches → último es incompleto
        
        Returns:
            Lista de tuplas (in_log, out_log)
        """
        same_day_overnight = bool(
            shift
            and shift.is_overnight_shift
            and len({log.date for log in daily_logs}) == 1
            and any(log.time >= shift.expected_in for log in daily_logs)
        )

        def chronological_key(log):
            adjusted_date = log.date
            if same_day_overnight and log.time < shift.expected_in:
                adjusted_date += timedelta(days=1)
            return adjusted_date, log.time, log.id or 0

        ordered = sorted(daily_logs, key=chronological_key)
        mark_types = {log.mark_type for log in ordered}
        pairs = []

        if 0 in mark_types and 1 in mark_types:
            pending_in = None
            for log in ordered:
                if log.mark_type == 0:
                    pending_in = log
                elif log.mark_type == 1 and pending_in is not None:
                    pairs.append((pending_in, log))
                    pending_in = None
            return pairs

        # Dispositivos sin dirección confiable (p.ej. Hikvision básico):
        # alternar cronológicamente IN/OUT.
        for index in range(0, len(ordered) - 1, 2):
            pairs.append((ordered[index], ordered[index + 1]))
        return pairs
