"""Regresiones de la ruta de actualización SQLite para la edición desktop."""
import sqlite3

import pytest

from migrate_sqlite import configured_sqlite_path, migrate
from services import setup_service
from services.validators import ProcessedAttendanceValidator


def test_sqlite_migration_upgrades_legacy_workflow_schema(tmp_path):
    db_path = tmp_path / "attendance.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE auth_user (id INTEGER PRIMARY KEY, username VARCHAR, password_hash VARCHAR);
        INSERT INTO auth_user (username, password_hash) VALUES ('admin', 'hash');
        CREATE TABLE users (id INTEGER PRIMARY KEY, identifier VARCHAR);
        CREATE TABLE shifts (id INTEGER PRIMARY KEY, name VARCHAR, expected_in TIME, expected_out TIME);
        CREATE TABLE attendance_log (id INTEGER PRIMARY KEY);
        CREATE TABLE processed_attendance (
            id INTEGER PRIMARY KEY, employee_id INTEGER, date DATE, status VARCHAR(20)
        );
        CREATE TABLE device_terminal (id INTEGER PRIMARY KEY, name VARCHAR);
        """
    )
    connection.commit()
    connection.close()

    migrate(db_path)

    connection = sqlite3.connect(db_path)
    try:
        columns = {
            table: {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            for table in ("auth_user", "users", "processed_attendance", "device_terminal")
        }
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        connection.close()

    assert "token_version" in columns["auth_user"]
    assert "terminal_privilege" in columns["users"]
    assert {"previous_status", "pending_first_in", "pending_last_out", "pending_justification", "requested_by"}.issubset(columns["processed_attendance"])
    assert {
        "connection_params", "pull_schedule_enabled", "pull_schedule_mode", "pull_interval_minutes",
        "pull_schedule_weekdays", "pull_schedule_time", "pull_schedule_start_date", "pull_schedule_end_date",
        "pull_window_start", "pull_window_end", "next_pull_at",
        "last_pull_status", "last_pull_error",
    }.issubset(columns["device_terminal"])
    assert "holidays" in tables


def test_absent_status_is_valid_for_all_engines():
    assert ProcessedAttendanceValidator.validate_status("AUSENTE") == (True, None)


def test_sqlite_migration_uses_configured_database_path(monkeypatch, tmp_path):
    configured_path = tmp_path / "desktop-data.db"
    monkeypatch.setenv("DB_ENGINE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(configured_path))

    assert configured_sqlite_path() == configured_path


def test_sqlite_migration_rejects_postgres_configuration(monkeypatch):
    monkeypatch.setenv("DB_ENGINE", "postgres")

    with pytest.raises(RuntimeError, match="DB_ENGINE=sqlite"):
        configured_sqlite_path()


def test_sqlite_profile_is_ready_for_local_first_run(monkeypatch):
    monkeypatch.setenv("DB_ENGINE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", "desktop-data.db")

    assert setup_service.is_database_configured() is True
