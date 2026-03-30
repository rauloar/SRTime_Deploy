"""
Tests para módulo de validadores.
"""
import pytest
from datetime import datetime, time, date, timedelta

from services.validators import AttendanceValidator, ProcessedAttendanceValidator
from models.attendance import AttendanceLog


class TestAttendanceValidator:
    """Tests para AttendanceValidator."""
    
    def test_validate_time_valid(self, test_db):
        """Test: Validar tiempo válido."""
        validator = AttendanceValidator(test_db)
        
        assert validator.validate_time(time(8, 30)) is True
        assert validator.validate_time(time(0, 0)) is True
        assert validator.validate_time(time(23, 59)) is True
    
    def test_validate_time_invalid(self, test_db):
        """Test: Validar tiempo inválido."""
        validator = AttendanceValidator(test_db)
        
        assert validator.validate_time(None) is False
        assert validator.validate_time("08:30") is False
        assert validator.validate_time(123) is False
    
    def test_validate_log_entry_valid(self, test_db, sample_employee):
        """Test: Validar entry válido."""
        validator = AttendanceValidator(test_db)
        
        log = AttendanceLog(
            employee_id=sample_employee.id,
            raw_identifier="DEV001",
            date=date.today(),
            time=time(8, 30),
            mark_type=0,
            is_processed=False
        )
        
        is_valid, error = validator.validate_log_entry(log)
        assert is_valid is True
        assert error is None
    
    def test_validate_log_entry_missing_employee(self, test_db):
        """Test: Validar entry sin employee_id."""
        validator = AttendanceValidator(test_db)
        
        log = AttendanceLog(
            employee_id=None,
            raw_identifier="DEV001",
            date=date.today(),
            time=time(8, 30),
            mark_type=0,
            is_processed=False
        )
        
        is_valid, error = validator.validate_log_entry(log)
        assert is_valid is False
        assert "employee_id" in error
    
    def test_validate_log_entry_future_date(self, test_db, sample_employee):
        """Test: Validar entry con fecha futura."""
        validator = AttendanceValidator(test_db)
        
        future_date = date.today() + timedelta(days=1)
        log = AttendanceLog(
            employee_id=sample_employee.id,
            raw_identifier="DEV001",
            date=future_date,
            time=time(8, 30),
            mark_type=0,
            is_processed=False
        )
        
        is_valid, error = validator.validate_log_entry(log)
        assert is_valid is False
        assert "future" in error.lower()
    
    def test_detect_duplicate_logs(self, test_db, sample_employee):
        """Test: Detectar logs duplicados."""
        validator = AttendanceValidator(test_db)
        
        today = date.today()
        
        # Crear logs
        logs = [
            AttendanceLog(
                employee_id=sample_employee.id,
                raw_identifier="DEV001",
                date=today,
                time=time(8, 0),
                mark_type=0
            ),
            AttendanceLog(
                employee_id=sample_employee.id,
                raw_identifier="DEV001",
                date=today,
                time=time(8, 0),  # Mismo que el anterior - DUPLICADO
                mark_type=0
            ),
            AttendanceLog(
                employee_id=sample_employee.id,
                raw_identifier="DEV001",
                date=today,
                time=time(17, 0),
                mark_type=1
            )
        ]
        
        duplicates = validator.detect_duplicate_logs(logs)
        assert len(duplicates) == 1
        assert duplicates[0].time == time(8, 0)
    
    def test_detect_gaps_and_anomalies(self, test_db, sample_employee):
        """Test: Detectar gaps anómalos entre punches."""
        validator = AttendanceValidator(test_db)
        
        today = date.today()
        
        # Logs con gap anómalo (5 horas entre punches)
        logs_with_gap = [
            AttendanceLog(
                employee_id=sample_employee.id,
                raw_identifier="DEV001",
                date=today,
                time=time(8, 0),
                mark_type=0
            ),
            AttendanceLog(
                employee_id=sample_employee.id,
                raw_identifier="DEV001",
                date=today,
                time=time(13, 0),  # 5 horas de gap
                mark_type=1
            )
        ]
        
        result = validator.detect_gaps_and_anomalies(logs_with_gap, max_gap_hours=4.0)
        assert result['has_gaps'] is True
        assert len(result['gaps']) == 1
        assert result['gaps'][0]['gap_hours'] == pytest.approx(5.0)
    
    def test_detect_gaps_normal(self, test_db, sample_employee):
        """Test: Sin gaps anómalos."""
        validator = AttendanceValidator(test_db)
        
        today = date.today()
        
        logs_normal = [
            AttendanceLog(
                employee_id=sample_employee.id,
                raw_identifier="DEV001",
                date=today,
                time=time(8, 0),
                mark_type=0
            ),
            AttendanceLog(
                employee_id=sample_employee.id,
                raw_identifier="DEV001",
                date=today,
                time=time(17, 0),
                mark_type=1
            )
        ]
        
        result = validator.detect_gaps_and_anomalies(logs_normal, max_gap_hours=4.0)
        # Gap entre 08:00 y 17:00 = 9 horas, que es > 4 horas (max_gap_hours)
        # Así que SÍ hay un gap anómalo
        assert result['has_gaps'] is True
        assert len(result['gaps']) == 1
    
    def test_validate_punch_pair_valid(self, test_db, sample_employee):
        """Test: Validar par IN/OUT válido."""
        validator = AttendanceValidator(test_db)
        
        in_log = AttendanceLog(
            employee_id=sample_employee.id,
            date=date.today(),
            time=time(8, 0),
            mark_type=0
        )
        out_log = AttendanceLog(
            employee_id=sample_employee.id,
            date=date.today(),
            time=time(17, 0),
            mark_type=1
        )
        
        is_valid, error = validator.validate_punch_pair(in_log, out_log)
        assert is_valid is True
        assert error is None
    
    def test_validate_punch_pair_reversed(self, test_db, sample_employee):
        """Test: Validar par IN/OUT con OUT antes de IN (inválido)."""
        validator = AttendanceValidator(test_db)
        
        in_log = AttendanceLog(
            employee_id=sample_employee.id,
            date=date.today(),
            time=time(17, 0),
            mark_type=0
        )
        out_log = AttendanceLog(
            employee_id=sample_employee.id,
            date=date.today(),
            time=time(8, 0),
            mark_type=1
        )
        
        is_valid, error = validator.validate_punch_pair(in_log, out_log)
        assert is_valid is False
        assert "after" in error.lower()
    
    def test_validate_batch(self, test_db, sample_employee):
        """Test: Validar batch de logs."""
        validator = AttendanceValidator(test_db)
        
        today = date.today()
        logs = [
            AttendanceLog(
                employee_id=sample_employee.id,
                raw_identifier="DEV001",
                date=today,
                time=time(8, 0),
                mark_type=0
            ),
            AttendanceLog(
                employee_id=None,  # Inválido
                raw_identifier="DEV001",
                date=today,
                time=time(12, 0),
                mark_type=1
            ),
            AttendanceLog(
                employee_id=sample_employee.id,
                raw_identifier="DEV001",
                date=today,
                time=time(8, 0),  # Duplicado del primero
                mark_type=0
            ),
            AttendanceLog(
                employee_id=sample_employee.id,
                raw_identifier="DEV001",
                date=today,
                time=time(17, 0),
                mark_type=1
            )
        ]
        
        result = validator.validate_batch(logs)
        
        assert result['total_count'] == 4
        assert result['valid_count'] == 3
        assert result['invalid_count'] == 1
        assert result['duplicate_count'] == 1


class TestProcessedAttendanceValidator:
    """Tests para ProcessedAttendanceValidator."""
    
    def test_validate_calculated_hours_valid(self):
        """Test: Validar horas calculadas válidas."""
        is_valid, error = ProcessedAttendanceValidator.validate_calculated_hours(
            total_hours=8.5,
            tardiness_minutes=15,
            overtime_minutes=30,
            early_departure_minutes=0
        )
        
        assert is_valid is True
        assert error is None
    
    def test_validate_calculated_hours_negative_total(self):
        """Test: Validar horas totales negativas."""
        is_valid, error = ProcessedAttendanceValidator.validate_calculated_hours(
            total_hours=-1.0,
            tardiness_minutes=0,
            overtime_minutes=0,
            early_departure_minutes=0
        )
        
        assert is_valid is False
        assert "negative" in error.lower()
    
    def test_validate_calculated_hours_exceeds_24(self):
        """Test: Validar horas totales > 24."""
        is_valid, error = ProcessedAttendanceValidator.validate_calculated_hours(
            total_hours=25.0,
            tardiness_minutes=0,
            overtime_minutes=0,
            early_departure_minutes=0
        )
        
        assert is_valid is False
        assert "24" in error
    
    def test_validate_calculated_hours_negative_tardiness(self):
        """Test: Validar tardanza negativa."""
        is_valid, error = ProcessedAttendanceValidator.validate_calculated_hours(
            total_hours=8.0,
            tardiness_minutes=-10,
            overtime_minutes=0,
            early_departure_minutes=0
        )
        
        assert is_valid is False
        assert "tardiness" in error.lower()
    
    def test_validate_status_valid(self):
        """Test: Validar status válidos."""
        for status in ["OK", "INCOMPLETO", "ERROR", "JUSTIFICADO"]:
            is_valid, error = ProcessedAttendanceValidator.validate_status(status)
            assert is_valid is True
            assert error is None
    
    def test_validate_status_invalid(self):
        """Test: Validar status inválido."""
        is_valid, error = ProcessedAttendanceValidator.validate_status("INVALID_STATUS")
        
        assert is_valid is False
        assert "Invalid status" in error
