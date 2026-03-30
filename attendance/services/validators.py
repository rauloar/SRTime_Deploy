"""
Validators para datos de Attendance.
Validaciones de integridad, duplicados y datos anómalos.
"""
from datetime import datetime, time as Time, date
from sqlalchemy.orm import Session
from models.attendance import AttendanceLog
from typing import List, Tuple, Optional, Dict


class AttendanceValidator:
    """Validador centralizado para records de asistencia."""
    
    def __init__(self, session: Session):
        self.session = session
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []
    
    def validate_time(self, t: time | None) -> bool:
        """Valida que el tiempo esté en rango válido (no es ni None)."""
        if t is None:
            return False
        if not isinstance(t, Time):
            return False
        return True
    
    def validate_log_entry(self, log: AttendanceLog) -> Tuple[bool, Optional[str]]:
        """
        Valida un entry individual de AttendanceLog.
        
        Returns:
            (is_valid, error_message)
        """
        # Validar employee_id
        if not log.employee_id:
            return False, "employee_id is missing"
        
        # Validar fecha
        if not isinstance(log.date, date):
            return False, f"Invalid date: {log.date}"
        
        # Validar hora
        if not self.validate_time(log.time):
            return False, f"Invalid time: {log.time}"
        
        # Validar que no sea fecha futura
        today = datetime.now().date()
        if log.date > today:
            return False, f"Attendance log date in future: {log.date}"
        
        # Validar que no sea muy antigua (más de 1 año)
        from datetime import timedelta
        one_year_ago = today - timedelta(days=365)
        if log.date < one_year_ago:
            return False, f"Attendance log too old: {log.date}"
        
        return True, None
    
    def detect_duplicate_logs(self, logs: List[AttendanceLog]) -> List[AttendanceLog]:
        """
        Detecta logs duplicados en la lista.
        Duplicado = mismo employee_id, date, time, mark_type.
        
        Returns:
            Lista de logs que son duplicados
        """
        seen = {}
        duplicates = []
        
        for log in logs:
            key = (log.employee_id, log.date, log.time, log.mark_type)
            if key in seen:
                duplicates.append(log)
            else:
                seen[key] = log
        
        return duplicates
    
    def detect_gaps_and_anomalies(
        self, 
        daily_logs: List[AttendanceLog],
        max_gap_hours: float = 4.0
    ) -> Dict:
        """
        Detecta gaps anómalos entre punches consecutivos.
        Un gap > max_gap_hours es sospechoso (posible OUT sin IN o vice versa).
        
        Args:
            daily_logs: Logs ordenados por hora del mismo día
            max_gap_hours: Gap máximo esperado (default 4 horas)
        
        Returns:
            {
                'has_gaps': bool,
                'gaps': [{'time_from': time, 'time_to': time, 'gap_hours': float}]
            }
        """
        result = {'has_gaps': False, 'gaps': []}
        
        if len(daily_logs) < 2:
            return result
        
        for i in range(len(daily_logs) - 1):
            from datetime import datetime
            time_from = daily_logs[i].time
            time_to = daily_logs[i + 1].time
            
            dt_from = datetime.combine(datetime.now().date(), time_from)
            dt_to = datetime.combine(datetime.now().date(), time_to)
            
            gap_hours = (dt_to - dt_from).total_seconds() / 3600.0
            
            if gap_hours > max_gap_hours:
                result['has_gaps'] = True
                result['gaps'].append({
                    'index_from': i,
                    'index_to': i + 1,
                    'time_from': str(time_from),
                    'time_to': str(time_to),
                    'gap_hours': round(gap_hours, 2)
                })
        
        return result
    
    def validate_punch_pair(
        self, 
        in_log: AttendanceLog, 
        out_log: AttendanceLog
    ) -> Tuple[bool, Optional[str]]:
        """
        Valida que un par IN/OUT sea válido.
        
        Returns:
            (is_valid, error_message)
        """
        # OUT debe ser después de IN
        if out_log.time <= in_log.time:
            return False, f"OUT time ({out_log.time}) must be after IN time ({in_log.time})"
        
        # Máximo 12 horas de diferencia (safeguard)
        from datetime import datetime
        dt_in = datetime.combine(datetime.now().date(), in_log.time)
        dt_out = datetime.combine(datetime.now().date(), out_log.time)
        
        hours = (dt_out - dt_in).total_seconds() / 3600.0
        if hours > 24:
            return False, f"Punch pair span too long ({hours:.1f} hours)"
        
        return True, None
    
    def validate_batch(self, logs: List[AttendanceLog]) -> Dict:
        """
        Valida un lote de logs.
        
        Returns:
            {
                'valid_count': int,
                'invalid_count': int,
                'duplicate_count': int,
                'errors': [],
                'warnings': [],
                'duplicates': []
            }
        """
        valid_count = 0
        invalid_logs = []
        
        # Validar cada log
        for log in logs:
            is_valid, error_msg = self.validate_log_entry(log)
            if is_valid:
                valid_count += 1
            else:
                invalid_logs.append({
                    'log_id': log.id,
                    'employee_id': log.employee_id,
                    'error': error_msg
                })
        
        # Detectar duplicados
        duplicates = self.detect_duplicate_logs(logs)
        
        return {
            'total_count': len(logs),
            'valid_count': valid_count,
            'invalid_count': len(invalid_logs),
            'duplicate_count': len(duplicates),
            'invalid_logs': invalid_logs,
            'duplicates': [
                {
                    'id': d.id,
                    'employee_id': d.employee_id,
                    'date': str(d.date),
                    'time': str(d.time)
                }
                for d in duplicates
            ]
        }


class ProcessedAttendanceValidator:
    """Validador para records de asistencia procesada."""
    
    @staticmethod
    def validate_calculated_hours(
        total_hours: float,
        tardiness_minutes: int,
        overtime_minutes: int,
        early_departure_minutes: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Validaciones básicas en los valores calculados.
        """
        if total_hours < 0:
            return False, "total_hours cannot be negative"
        
        if total_hours > 24:
            return False, "total_hours cannot exceed 24"
        
        if tardiness_minutes < 0:
            return False, "tardiness_minutes cannot be negative"
        
        if overtime_minutes < 0:
            return False, "overtime_minutes cannot be negative"
        
        if early_departure_minutes < 0:
            return False, "early_departure_minutes cannot be negative"
        
        return True, None
    
    @staticmethod
    def validate_status(status: str) -> Tuple[bool, Optional[str]]:
        """Valida que el status sea uno de los valores permitidos."""
        valid_statuses = ["OK", "INCOMPLETO", "ERROR", "JUSTIFICADO"]
        
        if status not in valid_statuses:
            return False, f"Invalid status '{status}'. Must be one of: {valid_statuses}"
        
        return True, None
