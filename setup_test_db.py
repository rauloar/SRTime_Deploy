#!/usr/bin/env python3
"""Quick script to create SQLite database for testing."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'attendance'))

from core.database import engine, Base

print("[INFO] Creating database...")
Base.metadata.create_all(engine)

db_path = os.path.join(os.path.dirname(__file__), "attendance.db")
if os.path.exists(db_path):
    print(f"[OK] Database created: {db_path}")
else:
    print(f"[ERROR] Database not found at {db_path}")
    sys.exit(1)
