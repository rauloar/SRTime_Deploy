"""
Script para verificar que todos los módulos se importan correctamente sin errores.
"""
import sys
import os

# Path setup
root_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, root_dir)

def check_imports():
    """Verifica que todos los módulos importan sin errores."""
    print("🔍 Verificando imports...\n")
    
    modules_to_check = [
        ('models.attendance', 'AttendanceLog'),
        ('models.employee', 'User'),
        ('models.shift', 'Shift'),
        ('models.processed_attendance', 'ProcessedAttendance'),
        ('services.validators', 'AttendanceValidator'),
        ('services.engine', 'AttendanceEngine'),
    ]
    
    errors = []
    
    for module_name, class_name in modules_to_check:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"  ✓ {module_name}.{class_name}")
        except Exception as e:
            error_msg = f"  ✗ {module_name}.{class_name}: {str(e)}"
            print(error_msg)
            errors.append(error_msg)
    
    print()
    
    if errors:
        print(f"❌ {len(errors)} errores encontrados:")
        for error in errors:
            print(error)
        return False
    else:
        print("✅ Todos los módulos importan correctamente")
        return True


def check_syntax():
    """Verifica que no haya errores de sintaxis."""
    print("\n🔍 Verificando sintaxis...\n")
    
    files_to_check = [
        'models/shift.py',
        'services/validators.py',
        'services/engine.py',
    ]
    
    errors = []
    
    for file_path in files_to_check:
        full_path = os.path.join(root_dir, 'attendance', file_path)
        try:
            with open(full_path, 'r') as f:
                code = f.read()
                compile(code, file_path, 'exec')
            print(f"  ✓ {file_path}")
        except SyntaxError as e:
            error_msg = f"  ✗ {file_path}: {str(e)}"
            print(error_msg)
            errors.append(error_msg)
    
    print()
    
    if errors:
        print(f"❌ {len(errors)} errores de sintaxis encontrados:")
        for error in errors:
            print(error)
        return False
    else:
        print("✅ No hay errores de sintaxis")
        return True


def main():
    print("=" * 60)
    print("✅ VALIDACIÓN DE CÓDIGO")
    print("=" * 60)
    print()
    
    syntax_ok = check_syntax()
    imports_ok = check_imports()
    
    print("\n" + "=" * 60)
    if syntax_ok and imports_ok:
        print("✅ VALIDACIÓN COMPLETADA - TODO OK")
    else:
        print("❌ VALIDACIÓN FALLIDA - HAY ERRORES")
    print("=" * 60)
    
    return syntax_ok and imports_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
