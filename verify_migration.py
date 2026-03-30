#!/usr/bin/env python3
"""Verify that database migration was applied successfully."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'attendance'))

from core.database import engine
from sqlalchemy import inspect, text

def verify_shifts_table():
    """Verify the shifts table has the new columns."""
    inspector = inspect(engine)
    columns = inspector.get_columns('shifts')
    
    print("[OK] Shifts table columns (verification):")
    print("-" * 70)
    
    required_columns = {'is_overnight_shift', 'break_duration_minutes'}
    found_columns = set()
    
    for col in columns:
        nullable = "nullable" if col['nullable'] else "NOT NULL"
        col_type = str(col['type'])
        print(f"  - {col['name']:<30} {col_type:<20} {nullable}")
        
        if col['name'] in required_columns:
            found_columns.add(col['name'])
    
    print("-" * 70)
    
    if required_columns == found_columns:
        print("[OK] SUCCESS: All new columns found in shifts table!")
        
        # Verify with a sample query
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM shifts LIMIT 1"))
            count = result.scalar()
            print(f"[OK] Shifts table is accessible (contains {count} existing shift records)")
        return True
    else:
        missing = required_columns - found_columns
        print(f"[ERROR] Missing columns: {missing}")
        return False

def check_migration_history():
    """Check the alembic version history."""
    inspector = inspect(engine)
    
    # Try to check if alembic_version table exists
    if 'alembic_version' in inspector.get_table_names():
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1"))
            row = result.fetchone()
            if row:
                print(f"\n[OK] Current migration version: {row[0]}")

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("DATABASE MIGRATION VERIFICATION")
    print("=" * 70 + "\n")
    
    try:
        success = verify_shifts_table()
        check_migration_history()
        
        if success:
            print("\n[OK] Migration verification PASSED!")
            sys.exit(0)
        else:
            print("\n[ERROR] Migration verification FAILED!")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
