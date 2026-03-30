#!/usr/bin/env python3
"""Initialize SQLite database for testing migrations."""

import sys
import os

# Add attendance directory to path
sys.path.insert(0, os.path.dirname(__file__))

from core.database import engine, Base

# Create all tables
print("[INFO] Creating SQLite database schema...")
Base.metadata.create_all(engine)
print("[OK] Database schema created successfully")

# Verify connection
try:
    with engine.connect() as conn:
        result = conn.execute("SELECT 1")
        print("[OK] Database connection verified")
except Exception as e:
    print(f"[ERROR] Failed to verify database: {e}")
    sys.exit(1)

print("[DONE] Database initialization complete")
