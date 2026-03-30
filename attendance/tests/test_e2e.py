"""
Script de prueba end-to-end para el Attendance Engine.
Simula un flujo completo de procesamiento.
"""
import sys
from datetime import datetime, time, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Importar modelos y servicios
sys.path.insert(0, '.')
from core.database import Base
from models.shift import Shift
from models.employee import User
from models.attendance import AttendanceLog
from models.processed_attendance import ProcessedAttendance
from services.engine import AttendanceEngine
from services.validators import AttendanceValidator


def setup_test_database(db_url='sqlite:///test_attendance.db'):
    """Configura base de datos de prueba."""
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session


def create_test_data(session):
    """Crea datos de prueba."""
    print("📝 Creando datos de prueba...")
    
    # Crear turnos
    morning_shift = Shift(
        name="Morning Shift",
        expected_in=time(8, 0),
        expected_out=time(17, 0),
        grace_period_minutes=15,
        is_overnight_shift=False,
        break_duration_minutes=60
    )
    
    night_shift = Shift(
        name="Night Shift",
        expected_in=time(22, 0),
        expected_out=time(6, 0),
        grace_period_minutes=15,
        is_overnight_shift=True,
        break_duration_minutes=30
    )
    
    session.add_all([morning_shift, night_shift])
    session.commit()
    
    # Crear empleados
    emp1 = User(
        identifier="EMP001",
        first_name="Juan",
        last_name="Díaz",
        shift_id=morning_shift.id,
        is_active=True
    )
    
    emp2 = User(
        identifier="EMP002",
        first_name="María",
        last_name="García",
        shift_id=night_shift.id,
        is_active=True
    )
    
    session.add_all([emp1, emp2])
    session.commit()
    
    # Crear logs de asistencia
    today = date.today()
    
    print("  → Empleado 1 (Turno Mañana):")
    # Caso 1: Día normal (punctual)
    session.add(AttendanceLog(
        employee_id=emp1.id,
        raw_identifier="DEV001",
        date=today,
        time=time(8, 5),
        mark_type=0,
        is_processed=False
    ))
    session.add(AttendanceLog(
        employee_id=emp1.id,
        raw_identifier="DEV001",
        date=today,
        time=time(17, 0),
        mark_type=1,
        is_processed=False
    ))
    print("    ✓ Logs día normal (08:05 - 17:00)")
    
    # Caso 2: Día tardío
    yesterday = today - timedelta(days=1)
    session.add(AttendanceLog(
        employee_id=emp1.id,
        raw_identifier="DEV001",
        date=yesterday,
        time=time(8, 45),  # 45 min tarde
        mark_type=0,
        is_processed=False
    ))
    session.add(AttendanceLog(
        employee_id=emp1.id,
        raw_identifier="DEV001",
        date=yesterday,
        time=time(19, 0),  # 2 horas de overtime
        mark_type=1,
        is_processed=False
    ))
    print("    ✓ Logs día tardío (08:45 - 19:00) con overtime")
    
    print("  → Empleado 2 (Turno Noche):")
    # Caso 3: Turno nocturno
    session.add(AttendanceLog(
        employee_id=emp2.id,
        raw_identifier="DEV002",
        date=today,
        time=time(22, 0),
        mark_type=0,
        is_processed=False
    ))
    session.add(AttendanceLog(
        employee_id=emp2.id,
        raw_identifier="DEV002",
        date=today,
        time=time(6, 30),
        mark_type=1,
        is_processed=False
    ))
    print("    ✓ Logs turno nocturno (22:00 - 06:30)")
    
    # Caso 4: Múltiples entradas/salidas
    two_days_ago = today - timedelta(days=2)
    session.add(AttendanceLog(
        employee_id=emp1.id,
        raw_identifier="DEV001",
        date=two_days_ago,
        time=time(8, 0),
        mark_type=0,
        is_processed=False
    ))
    session.add(AttendanceLog(
        employee_id=emp1.id,
        raw_identifier="DEV001",
        date=two_days_ago,
        time=time(12, 0),
        mark_type=1,
        is_processed=False
    ))
    session.add(AttendanceLog(
        employee_id=emp1.id,
        raw_identifier="DEV001",
        date=two_days_ago,
        time=time(13, 0),
        mark_type=0,
        is_processed=False
    ))
    session.add(AttendanceLog(
        employee_id=emp1.id,
        raw_identifier="DEV001",
        date=two_days_ago,
        time=time(17, 0),
        mark_type=1,
        is_processed=False
    ))
    print("    ✓ Logs con múltiples entradas/salidas (08:00-12:00, 13:00-17:00)")
    
    session.commit()
    print("✅ Datos de prueba creados\n")
    
    return emp1, emp2


def validate_data(session):
    """Valida los logs antes de procesar."""
    print("🔍 Validando logs...")
    
    validator = AttendanceValidator(session)
    logs = session.query(AttendanceLog).all()
    
    result = validator.validate_batch(logs)
    
    print(f"  Total logs: {result['total_count']}")
    print(f"  ✓ Válidos: {result['valid_count']}")
    print(f"  ✗ Inválidos: {result['invalid_count']}")
    print(f"  ⚠ Duplicados: {result['duplicate_count']}")
    
    if result['invalid_count'] > 0:
        print("  Logs inválidos:")
        for log in result['invalid_logs']:
            print(f"    - Log {log['log_id']}: {log['error']}")
    
    print()
    return result['valid_count'] == result['total_count']


def process_attendance(session):
    """Procesa la asistencia."""
    print("⚙️ Procesando logs de asistencia...")
    
    engine = AttendanceEngine(session)
    
    def progress(count, total):
        print(f"  Procesados: {count}/{total}")
    
    count = engine.process_all(progress_callback=progress, force_all=False)
    
    if engine.processed_with_errors:
        print(f"  ⚠ {len(engine.processed_with_errors)} errores durante el procesamiento:")
        for error in engine.processed_with_errors:
            print(f"    - {error['employee_id']} ({error['date']}): {error['error']}")
    
    print(f"✅ {count} días procesados\n")
    return count


def display_results(session):
    """Muestra resultados del procesamiento."""
    print("📊 RESULTADOS DEL PROCESAMIENTO:\n")
    
    records = session.query(ProcessedAttendance).all()
    
    if not records:
        print("  ℹ No hay registros procesados")
        return
    
    for record in records:
        employee = session.query(User).filter_by(id=record.employee_id).first()
        emp_name = f"{employee.first_name} {employee.last_name}" if employee else "Unknown"
        
        print(f"📅 {emp_name} - {record.date}")
        print(f"   IN: {record.first_in} | OUT: {record.last_out}")
        print(f"   Horas trabajadas: {record.total_hours}")
        print(f"   Estado: {record.status}")
        
        if record.tardiness_minutes > 0:
            print(f"   ⏰ Tardanza: {record.tardiness_minutes} min")
        
        if record.early_departure_minutes > 0:
            print(f"   🚪 Salida temprana: {record.early_departure_minutes} min")
        
        if record.overtime_minutes > 0:
            print(f"   ⏱️  Overtime: {record.overtime_minutes} min")
        
        if record.justification:
            print(f"   Justificación: {record.justification}")
        
        print()


def test_overnight_detection(test_db):
    """Test: Verificar que overnight shifts se calculan correctamente."""
    print("🌙 TEST: Validación de Turnos Nocturnos\n")
    
    records = test_db.query(ProcessedAttendance).join(
        User, ProcessedAttendance.employee_id == User.id
    ).join(
        Shift, User.shift_id == Shift.id
    ).filter(Shift.is_overnight_shift == True).all()
    
    if not records:
        print("  ℹ No hay registros nocturnos")
        return True
    
    for record in records:
        employee = session.query(User).filter_by(id=record.employee_id).first()
        
        # Verificar que last_out < first_in (característica de overnight)
        if record.last_out and record.first_in:
            is_overnight = record.last_out < record.first_in
            print(f"  {employee.first_name} {employee.last_name}:")
            print(f"    IN: {record.first_in}, OUT: {record.last_out}")
            print(f"    ✓ Detected as overnight: {is_overnight}")
            print(f"    Horas: {record.total_hours}")
            print()
    
    return True


def test_multiple_entries(test_db):
    """Test: Verificar que múltiples IN/OUT se suman correctamente."""
    print("🔄 TEST: Múltiples Entradas/Salidas\n")
    
    two_days_ago = date.today() - timedelta(days=2)
    record = test_db.query(ProcessedAttendance).filter_by(
        date=two_days_ago
    ).first()
    
    if not record:
        print("  ℹ No hay registros con múltiples entradas/salidas")
        return True
    
    print(f"  Registro: {record.date}")
    print(f"  Primera entrada: {record.first_in}")
    print(f"  Última salida: {record.last_out}")
    
    # Esperado: 08:00-12:00 (4h) + 13:00-17:00 (4h) - 1h break = 7h
    expected_hours = 7.0
    actual_hours = record.total_hours
    
    print(f"  Horas esperadas: ~{expected_hours}")
    print(f"  Horas calculadas: {actual_hours}")
    
    if abs(actual_hours - expected_hours) < 0.5:
        print(f"  ✓ Test PASSED")
        return True
    else:
        print(f"  ✗ Test FAILED")
        return False


def main():
    """Ejecuta la prueba end-to-end completa."""
    print("=" * 60)
    print("🧪 PRUEBA END-TO-END - ATTENDANCE ENGINE")
    print("=" * 60)
    print()
    
    # Setup
    engine, Session = setup_test_database()
    session = Session()
    
    try:
        # Crear datos
        emp1, emp2 = create_test_data(session)
        
        # Validar
        is_valid = validate_data(session)
        
        # Procesar
        count = process_attendance(session)
        
        # Mostrar resultados
        display_results(session)
        
        # Tests específicos
        test_overnight_detection(session)
        test_multiple_entries(session)
        
        print("=" * 60)
        print("✅ PRUEBA END-TO-END COMPLETADA")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()
