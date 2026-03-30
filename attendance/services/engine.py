from collections import defaultdict
from datetime import datetime, date, timedelta, time as Time
from sqlalchemy.orm import Session
import logging
from typing import Optional, List, Dict, Tuple

from models.attendance import AttendanceLog
from models.employee import User
from models.shift import Shift
from models.processed_attendance import ProcessedAttendance
from services.validators import AttendanceValidator, ProcessedAttendanceValidator


logger = logging.getLogger(__name__)


class AttendanceEngine:
    """
    Motor de procesamiento de asistencia.
    Convierte raw logs en ProcessedAttendance con cálculos de horas, tardanza, etc.
    
    Mejoras:
    - Soporte para turnos nocturnos (overnight shifts)
    - Matching inteligente de pares IN/OUT (no solo primero/último)
    - Validación robusta de datos
    - Manejo de excepciones con rollback
    - Logging detallado
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.validator = AttendanceValidator(session)
        self.pa_validator = ProcessedAttendanceValidator()
        self.processed_with_errors = []

    def process_all(self, progress_callback=None, force_all=False) -> int:
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

            # Validar logs antes de procesar
            validation_result = self.validator.validate_batch(logs)
            if validation_result['invalid_count'] > 0:
                logger.warning(
                    f"Found {validation_result['invalid_count']} invalid logs. "
                    f"Continuing with {validation_result['valid_count']} valid logs."
                )
            
            if validation_result['duplicate_count'] > 0:
                logger.warning(f"Found {validation_result['duplicate_count']} duplicate logs")

            # Group by (employee_id, date)
            grouped_logs = defaultdict(list)
            for log in logs:
                if log.employee_id:
                    grouped_logs[(log.employee_id, log.date)].append(log)

            processed_count = 0
            total_days = len(grouped_logs)

            # Process each day for each employee
            for (emp_id, day), daily_logs in grouped_logs.items():
                if not daily_logs:
                    continue

                try:
                    employee = self.session.query(User).filter_by(id=emp_id).first()
                    if not employee: 
                        logger.warning(f"Employee {emp_id} not found, skipping")
                        continue
                    
                    # Check if already manually justified
                    existing = self.session.query(ProcessedAttendance).filter_by(
                        employee_id=emp_id, date=day
                    ).first()
                    
                    if existing and existing.status == "JUSTIFICADO":
                        processed_count += 1
                        if progress_callback and processed_count % 10 == 0:
                            progress_callback(processed_count, total_days)
                        continue
                    
                    shift = (self.session.query(Shift)
                            .filter_by(id=employee.shift_id)
                            .first() if employee.shift_id else None)
                    
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
            # Match IN/OUT pairs
            punch_pairs = self._match_punch_pairs(daily_logs)
            
            if not punch_pairs:
                return {'success': False, 'error': 'No valid punch pairs found'}
            
            # Calculate hours and metrics
            first_in_time = punch_pairs[0][0].time
            last_out_time = punch_pairs[-1][1].time
            
            total_hours = self._calculate_total_hours(punch_pairs, day, shift)
            tardiness, early_departure, overtime = self._calculate_metrics(
                day, first_in_time, last_out_time, shift
            )
            
            # Validate calculated values
            is_valid, error_msg = self.pa_validator.validate_calculated_hours(
                total_hours, tardiness, overtime, early_departure
            )
            if not is_valid:
                return {'success': False, 'error': f'Validation failed: {error_msg}'}
            
            # Determine status
            status = "OK"
            if not last_out_time:
                status = "INCOMPLETO"
            
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
        
        except Exception as e:
            logger.error(f"Error in _process_daily_logs: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _match_punch_pairs(self, daily_logs: List[AttendanceLog]) -> List[Tuple[AttendanceLog, AttendanceLog]]:
        """
        Empareja punches IN/OUT inteligentemente.
        
        Estrategia:
        1. Si existe mark_type, usarlo para diferenciar IN vs OUT
        2. Si no, asumir patrón alternado: IN, OUT, IN, OUT...
        3. Si número impar de punches → último es incompleto
        
        Returns:
            Lista de tuplas (in_log, out_log)
        """
        if len(daily_logs) < 2:
            return []
        
        pairs = []
        
        # Intentar usar mark_type si existe
        in_logs = []
        out_logs = []
        
        for log in daily_logs:
            # Asumir: mark_type 0 = IN, 1 = OUT (típico en sistemas de asistencia)
            # Si no existe mark_type, asumir alternado
            if log.mark_type == 0 or log.mark_type is None:
                in_logs.append(log)
            else:
                out_logs.append(log)
        
        # Si no hay diferenciación clara, usar heurística alternada
        if not in_logs and not out_logs:
            # Todos tienen mark_type igual o no usar mark_type
            for i in range(0, len(daily_logs) - 1, 2):
                in_log = daily_logs[i]
                out_log = daily_logs[i + 1]
                
                # Validar pareja
                is_valid, _ = self.validator.validate_punch_pair(in_log, out_log)
                if is_valid:
                    pairs.append((in_log, out_log))
        else:
            # Emparejar secuencialmente
            for i in range(min(len(in_logs), len(out_logs))):
                in_log = in_logs[i]
                out_log = out_logs[i]
                
                is_valid, _ = self.validator.validate_punch_pair(in_log, out_log)
                if is_valid:
                    pairs.append((in_log, out_log))
        
        return pairs if pairs else [(daily_logs[0], daily_logs[-1])]

    def _calculate_total_hours(
        self,
        punch_pairs: List[Tuple[AttendanceLog, AttendanceLog]],
        day: date,
        shift: Optional[Shift]
    ) -> float:
        """
        Calcula horas totales trabajadas desde los pares IN/OUT.
        Maneja turnos nocturnos.
        """
        total_seconds = 0
        
        for in_log, out_log in punch_pairs:
            in_dt = self._make_datetime(day, in_log.time, shift)
            out_dt = self._make_datetime(day, out_log.time, shift, is_expected_out=True)
            
            # Si es overnight, out_dt puede estar en el siguiente día
            if shift and shift.is_overnight_shift and out_log.time < in_log.time:
                out_dt = out_dt + timedelta(days=1)
            
            if out_dt > in_dt:
                total_seconds += (out_dt - in_dt).total_seconds()
        
        # Restar break si existe
        total_hours = total_seconds / 3600.0
        if shift and shift.break_duration_minutes:
            total_hours -= shift.break_duration_minutes / 60.0
        
        return max(0, total_hours)  # No negativos

    def _calculate_metrics(
        self,
        day: date,
        first_in_time: Time,
        last_out_time: Optional[Time],
        shift: Optional[Shift]
    ) -> Tuple[int, int, int]:
        """
        Calcula tardanza, salida temprana y overtime.
        
        Returns:
            (tardiness_minutes, early_departure_minutes, overtime_minutes)
        """
        tardiness = 0
        early_departure = 0
        overtime = 0
        
        if not shift or not first_in_time:
            return tardiness, early_departure, overtime
        
        # Tardanza
        expected_in_dt = self._make_datetime(day, shift.expected_in, shift)
        actual_in_dt = self._make_datetime(day, first_in_time, shift)
        
        diff_minutes = (actual_in_dt - expected_in_dt).total_seconds() / 60.0
        if diff_minutes > shift.grace_period_minutes:
            tardiness = int(diff_minutes)
        
        # Salida temprana y overtime
        if last_out_time:
            expected_out_dt = self._make_datetime(day, shift.expected_out, shift, is_expected_out=True)
            actual_out_dt = self._make_datetime(day, last_out_time, shift, is_expected_out=True)
            
            # Manejar overnight
            if shift.is_overnight_shift and last_out_time < shift.expected_out:
                actual_out_dt = actual_out_dt + timedelta(days=1)
            
            diff = (actual_out_dt - expected_out_dt).total_seconds() / 60.0
            
            if diff < 0:  # Salida temprana
                early_departure = int(-diff)
            elif diff > 0:  # Overtime
                overtime = int(diff)
        
        return tardiness, early_departure, overtime

    def _make_datetime(
        self,
        day: date,
        t: Time,
        shift: Optional[Shift] = None,
        is_expected_out: bool = False
    ) -> datetime:
        """
        Crea un datetime, manejando turnos nocturnos.
        
        Args:
            day: Fecha base
            t: Hora
            shift: Turno (para detectar overnight)
            is_expected_out: Si es hora de salida esperada
        
        Returns:
            datetime ajustado para overnight si es necesario
        """
        dt = datetime.combine(day, t)
        
        # Si es turno overnight y es salida, podría ser próximo día
        if shift and shift.is_overnight_shift and is_expected_out:
            if t < shift.expected_in:  # Ej: expected_in 22:00, expected_out 06:00
                dt = dt + timedelta(days=1)
        
        return dt

