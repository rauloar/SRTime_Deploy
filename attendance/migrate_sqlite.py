#!/usr/bin/env python3
"""
SQLite database migration script for SRTime.

This script applies schema migrations to SQLite databases locally.
- Does NOT recreate the database (safe for production/development databases)
- Applies missing columns/tables in-place
- Safe to run multiple times (idempotent)
- Creates a timestamped backup before applying changes

For PostgreSQL users, use Alembic: `alembic upgrade head`
For SQLite/standalone users, run this script: `python migrate_sqlite.py`
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
import bcrypt
import sys
import os
from dotenv import load_dotenv

# Auto-detect the same runtime directory used by core.database.
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENV_PATH = os.environ.get("SRTIME_ENV_FILE") or os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)


def configured_sqlite_path() -> Path:
    """Resolve the SQLite file with the exact convention used by core.database."""
    if os.getenv("DB_ENGINE", "sqlite").lower() != "sqlite":
        raise RuntimeError(
            "SQLite migration requires DB_ENGINE=sqlite. "
            "PostgreSQL upgrades use 'alembic upgrade head'."
        )

    db_path = Path(os.getenv("SQLITE_DB_PATH", "attendance.db"))
    return db_path if db_path.is_absolute() else Path(BASE_DIR) / db_path


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def table_exists(cur: sqlite3.Cursor, table_name: str) -> bool:
    """Check if table exists in database."""
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone() is not None


def column_exists(cur: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    """Check if column exists in table."""
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cur.fetchall()}
    return column_name in columns


def columns_of(cur: sqlite3.Cursor, table_name: str) -> set[str]:
    """Get all column names in a table."""
    cur.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cur.fetchall()}


def add_column_if_missing(
    cur: sqlite3.Cursor,
    table: str,
    column: str,
    ddl: str
) -> bool:
    """Add a column to table if it doesn't exist. Returns True if added."""
    if column_exists(cur, table, column):
        return False
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
    return True


def ensure_shifts_table(cur: sqlite3.Cursor) -> bool:
    """Ensure shifts table exists with all required columns."""
    if not table_exists(cur, "shifts"):
        cur.execute(
            """
            CREATE TABLE shifts (
                id INTEGER PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                expected_in TIME NOT NULL,
                expected_out TIME NOT NULL,
                grace_period_minutes INTEGER DEFAULT 15,
                is_overnight_shift BOOLEAN DEFAULT 0,
                break_duration_minutes INTEGER DEFAULT 0
            )
            """
        )
        return True
    return False


def migrate_auth_user(cur: sqlite3.Cursor, changed: list[str]) -> None:
    """Migrate auth_user table."""
    if not table_exists(cur, "auth_user"):
        return

    if add_column_if_missing(cur, "auth_user", "role", "role VARCHAR(20)"):
        changed.append("auth_user.role")
    
    if add_column_if_missing(cur, "auth_user", "must_change_password", "must_change_password BOOLEAN"):
        changed.append("auth_user.must_change_password")
    
    if add_column_if_missing(cur, "auth_user", "is_active", "is_active BOOLEAN DEFAULT 1"):
        changed.append("auth_user.is_active")

    if add_column_if_missing(cur, "auth_user", "token_version", "token_version INTEGER DEFAULT 0"):
        changed.append("auth_user.token_version")

    # Default values for existing records
    cur.execute("UPDATE auth_user SET role = 'viewer' WHERE role IS NULL OR role = ''")
    cur.execute("UPDATE auth_user SET must_change_password = 0 WHERE must_change_password IS NULL")
    cur.execute("UPDATE auth_user SET is_active = 1 WHERE is_active IS NULL")
    cur.execute("UPDATE auth_user SET token_version = 0 WHERE token_version IS NULL")
    
    # Ensure admin has root role
    cur.execute("UPDATE auth_user SET role = 'root' WHERE username = 'admin'")
    
    # Set default admin password if missing or empty
    cur.execute(
        """
        UPDATE auth_user
        SET password_hash = ?, is_active = 1, must_change_password = 1
        WHERE username = 'admin' AND (password_hash IS NULL OR password_hash = '')
        """,
        (hash_password("admin"),),
    )
    
    # Create admin user if no auth_user records exist
    cur.execute("SELECT COUNT(*) FROM auth_user")
    auth_count = int(cur.fetchone()[0] or 0)
    if auth_count == 0:
        cur.execute(
            """
            INSERT INTO auth_user (username, password_hash, is_active, role, must_change_password)
            VALUES (?, ?, 1, 'root', 1)
            """,
            ("admin", hash_password("admin")),
        )
        changed.append("auth_user (seed admin)")


def migrate_users(cur: sqlite3.Cursor, changed: list[str]) -> None:
    """Migrate users table."""
    if not table_exists(cur, "users"):
        return
    
    if add_column_if_missing(cur, "users", "shift_id", "shift_id INTEGER"):
        changed.append("users.shift_id")

    if add_column_if_missing(cur, "users", "terminal_privilege", "terminal_privilege INTEGER DEFAULT 0"):
        changed.append("users.terminal_privilege")

    if add_column_if_missing(cur, "users", "group_id", "group_id INTEGER"):
        changed.append("users.group_id")

    if add_column_if_missing(cur, "users", "shift_assignment_source", "shift_assignment_source VARCHAR(20) DEFAULT 'MANUAL'"):
        changed.append("users.shift_assignment_source")

    cur.execute("UPDATE users SET terminal_privilege = 0 WHERE terminal_privilege IS NULL")
    cur.execute("UPDATE users SET shift_assignment_source = 'MANUAL' WHERE shift_assignment_source IS NULL OR shift_assignment_source = ''")


def migrate_employee_groups(cur: sqlite3.Cursor, changed: list[str]) -> None:
    """Ensure employee groups table exists for bulk shift assignment."""
    if table_exists(cur, "employee_group"):
        return
    cur.execute(
        """
        CREATE TABLE employee_group (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            description VARCHAR,
            shift_id INTEGER,
            is_active BOOLEAN DEFAULT 1 NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY(shift_id) REFERENCES shifts(id)
        )
        """
    )
    changed.append("employee_group (table)")


def migrate_shifts(cur: sqlite3.Cursor, changed: list[str]) -> None:
    """Migrate shifts table - add overnight shift support."""
    if ensure_shifts_table(cur):
        changed.append("shifts (table)")
        return
    
    # Table exists, check for new columns
    if add_column_if_missing(
        cur,
        "shifts",
        "is_overnight_shift",
        "is_overnight_shift BOOLEAN DEFAULT 0"
    ):
        changed.append("shifts.is_overnight_shift")
    
    if add_column_if_missing(
        cur,
        "shifts",
        "break_duration_minutes",
        "break_duration_minutes INTEGER DEFAULT 0"
    ):
        changed.append("shifts.break_duration_minutes")
    
    # Ensure defaults for existing records
    cur.execute("UPDATE shifts SET is_overnight_shift = 0 WHERE is_overnight_shift IS NULL")
    cur.execute("UPDATE shifts SET break_duration_minutes = 0 WHERE break_duration_minutes IS NULL")


def migrate_attendance_log(cur: sqlite3.Cursor, changed: list[str]) -> None:
    """Migrate attendance_log table."""
    if not table_exists(cur, "attendance_log"):
        return
    
    if add_column_if_missing(
        cur,
        "attendance_log",
        "is_processed",
        "is_processed BOOLEAN DEFAULT 0"
    ):
        changed.append("attendance_log.is_processed")
    
    cur.execute("UPDATE attendance_log SET is_processed = 0 WHERE is_processed IS NULL")


def migrate_processed_attendance(cur: sqlite3.Cursor, changed: list[str]) -> None:
    """Create or upgrade processed attendance, including the workflow fields."""
    if not table_exists(cur, "processed_attendance"):
        cur.execute(
            """
            CREATE TABLE processed_attendance (
                id INTEGER PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                date DATE NOT NULL,
                first_in TIME,
                last_out TIME,
                total_hours FLOAT DEFAULT 0.0,
                tardiness_minutes INTEGER DEFAULT 0,
                early_departure_minutes INTEGER DEFAULT 0,
                overtime_minutes INTEGER DEFAULT 0,
                status VARCHAR(20) DEFAULT 'OK',
                justification VARCHAR,
                previous_status VARCHAR(20),
                pending_first_in TIME,
                pending_last_out TIME,
                pending_justification VARCHAR,
                requested_by VARCHAR,
                UNIQUE(employee_id, date),
                FOREIGN KEY(employee_id) REFERENCES users(id)
            )
            """
        )
        changed.append("processed_attendance (table)")
        return

    for column, ddl in [
        ("previous_status", "previous_status VARCHAR(20)"),
        ("pending_first_in", "pending_first_in TIME"),
        ("pending_last_out", "pending_last_out TIME"),
        ("pending_justification", "pending_justification VARCHAR"),
        ("requested_by", "requested_by VARCHAR"),
    ]:
        if add_column_if_missing(cur, "processed_attendance", column, ddl):
            changed.append(f"processed_attendance.{column}")


def migrate_holidays(cur: sqlite3.Cursor, changed: list[str]) -> None:
    if table_exists(cur, "holidays"):
        return
    cur.execute(
        """
        CREATE TABLE holidays (
            id INTEGER PRIMARY KEY,
            date DATE NOT NULL UNIQUE,
            name VARCHAR NOT NULL,
            is_recurring BOOLEAN DEFAULT 0
        )
        """
    )
    changed.append("holidays (table)")


def migrate_terminals(cur: sqlite3.Cursor, changed: list[str]) -> None:
    """Upgrade terminal configuration and local raw-pull scheduling fields."""
    if not table_exists(cur, "device_terminal"):
        return
    if add_column_if_missing(cur, "device_terminal", "connection_params", "connection_params JSON"):
        changed.append("device_terminal.connection_params")
    for column, ddl in [
        ("pull_schedule_enabled", "pull_schedule_enabled BOOLEAN DEFAULT 0"),
        ("pull_schedule_mode", "pull_schedule_mode VARCHAR(20) DEFAULT 'interval'"),
        ("pull_interval_minutes", "pull_interval_minutes INTEGER"),
        ("pull_schedule_weekdays", "pull_schedule_weekdays JSON"),
        ("pull_schedule_time", "pull_schedule_time TIME"),
        ("pull_schedule_start_date", "pull_schedule_start_date DATE"),
        ("pull_schedule_end_date", "pull_schedule_end_date DATE"),
        ("pull_window_start", "pull_window_start TIME"),
        ("pull_window_end", "pull_window_end TIME"),
        ("next_pull_at", "next_pull_at TIMESTAMP"),
        ("last_pull_status", "last_pull_status VARCHAR(20)"),
        ("last_pull_error", "last_pull_error VARCHAR(500)"),
    ]:
        if add_column_if_missing(cur, "device_terminal", column, ddl):
            changed.append(f"device_terminal.{column}")


def migrate(db_path: Path) -> None:
    """Execute all migrations on the database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    print(f"[INFO] Starting SQLite migration for: {db_path}")
    print()
    
    # Create backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}.bak_{ts}{db_path.suffix}")
    shutil.copy2(db_path, backup_path)
    print(f"[OK] Backup created: {backup_path.name}")
    
    # Connect and migrate
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    changed = []
    
    try:
        # Apply all migrations in order
        migrate_auth_user(cur, changed)
        migrate_employee_groups(cur, changed)
        migrate_users(cur, changed)
        migrate_shifts(cur, changed)
        migrate_attendance_log(cur, changed)
        migrate_processed_attendance(cur, changed)
        migrate_holidays(cur, changed)
        migrate_terminals(cur, changed)
        
        con.commit()
        
        # Validate final state
        cur.execute("SELECT COUNT(*) FROM auth_user WHERE is_active = 1")
        active_auth = int(cur.fetchone()[0] or 0)
        
    finally:
        con.close()
    
    # Report results
    print()
    if changed:
        print("[OK] Applied migrations:")
        for item in changed:
            print(f"  - {item}")
    else:
        print("[OK] Database is up-to-date. No schema changes were needed.")
    
    print()
    if active_auth == 0:
        print("[WARN] No active auth_user records found.")
    else:
        print(f"[OK] Active login users: {active_auth}")
    
    print()
    print("[DONE] SQLite migration finished successfully!")


if __name__ == "__main__":
    try:
        migrate(configured_sqlite_path())
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
