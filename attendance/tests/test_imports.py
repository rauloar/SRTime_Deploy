#!/usr/bin/env python3
"""
Validate all project modules can be imported without errors.
This ensures no syntax or import errors in core functionality.

Usage:
    python test_imports.py
"""

import sys
import os

# Path setup
root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, '..'))

def check_imports():
    """Verify all modules import without errors."""
    print("=" * 70)
    print("IMPORT VALIDATION")
    print("=" * 70 + "\n")
    
    modules_to_check = [
        ('models.attendance', 'AttendanceLog'),
        ('models.employee', 'User'),
        ('models.shift', 'Shift'),
        ('models.processed_attendance', 'ProcessedAttendance'),
        ('models.user', 'AuthUser'),
        ('services.validators', 'AttendanceValidator'),
        ('services.validators', 'ProcessedAttendanceValidator'),
        ('services.engine', 'AttendanceEngine'),
        ('core.database', 'SessionLocal'),
        ('core.init_db', 'init_db'),
    ]
    
    failed = []
    
    print("[INFO] Checking imports...\n")
    
    for module_name, class_name in modules_to_check:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"  [OK] {module_name}.{class_name}")
        except ImportError as e:
            print(f"  [ERROR] {module_name}.{class_name} - {e}")
            failed.append((module_name, class_name, str(e)))
        except AttributeError as e:
            print(f"  [ERROR] {module_name}.{class_name} not found - {e}")
            failed.append((module_name, class_name, str(e)))
        except Exception as e:
            print(f"  [ERROR] {module_name}.{class_name} - {type(e).__name__}: {e}")
            failed.append((module_name, class_name, str(e)))
    
    print()
    print("-" * 70)
    
    if failed:
        print(f"[ERROR] {len(failed)} import(s) failed!\n")
        for module, cls, error in failed:
            print(f"  - {module}.{cls}: {error}")
        return False
    else:
        print(f"[OK] All {len(modules_to_check)} modules imported successfully!")
        return True

def check_syntax():
    """Check Python files for syntax errors."""
    print("\n" + "=" * 70)
    print("SYNTAX VALIDATION")
    print("=" * 70 + "\n")
    
    import py_compile
    
    files_to_check = [
        'models/attendance.py',
        'models/employee.py',
        'models/shift.py',
        'models/processed_attendance.py',
        'models/user.py',
        'services/validators.py',
        'services/engine.py',
        'core/database.py',
    ]
    
    failed = []
    
    print("[INFO] Checking syntax...\n")
    
    for file_path in files_to_check:
        full_path = os.path.join(root_dir, file_path)
        try:
            py_compile.compile(full_path, doraise=True)
            print(f"  [OK] {file_path}")
        except py_compile.PyCompileError as e:
            print(f"  [ERROR] {file_path}")
            failed.append((file_path, str(e)))
    
    print()
    print("-" * 70)
    
    if failed:
        print(f"[ERROR] {len(failed)} syntax error(s) found!\n")
        for file_path, error in failed:
            print(f"  - {file_path}:\n    {error}")
        return False
    else:
        print(f"[OK] All {len(files_to_check)} files have valid syntax!")
        return True

if __name__ == "__main__":
    print()
    syntax_ok = check_syntax()
    imports_ok = check_imports()
    
    print()
    print("=" * 70)
    if syntax_ok and imports_ok:
        print("[OK] ALL VALIDATION CHECKS PASSED!")
        print("=" * 70 + "\n")
        sys.exit(0)
    else:
        print("[ERROR] VALIDATION FAILED!")
        print("=" * 70 + "\n")
        sys.exit(1)
