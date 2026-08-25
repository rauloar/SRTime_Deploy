import os
from core.database import engine, Base
from models import user, attendance
from models.employee import User
from models.holiday import Holiday  # noqa: F401 — registers Holiday with Base.metadata
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from pathlib import Path
from core.security import hash_password, verify_password
from models.user import AuthUser
from models.shift import Shift
from models.processed_attendance import ProcessedAttendance
from models.terminal import DeviceTerminal
from core.logging_config import get_logger

logger = get_logger(__name__)


def _should_initialize_on_startup() -> bool:
    """Initialize automatically only on first-run for SQLite databases."""
    if engine.url.get_backend_name() != "sqlite":
        return True

    db_file = engine.url.database
    if not db_file:
        return True

    return not Path(db_file).exists()

def init_database(target_engine=None, defer_admin_setup: bool = False):
    db_engine = target_engine or engine
    # create_all is idempotent: only creates missing tables, never drops existing ones.
    Base.metadata.create_all(bind=db_engine)

    logger.info("Initializing database schema...")
    session = Session(bind=db_engine)

    # Backward-compatible bootstrap for existing databases.
    auth_cols = {c["name"] for c in inspect(db_engine).get_columns("auth_user")}
    if "role" not in auth_cols:
        session.execute(text("ALTER TABLE auth_user ADD COLUMN role VARCHAR(20)"))
        session.commit()
    if "must_change_password" not in auth_cols:
        session.execute(text("ALTER TABLE auth_user ADD COLUMN must_change_password BOOLEAN"))
        session.commit()
    if "token_version" not in auth_cols:
        session.execute(text("ALTER TABLE auth_user ADD COLUMN token_version INTEGER DEFAULT 0 NOT NULL"))
        session.commit()

    users_cols = {c["name"] for c in inspect(db_engine).get_columns("users")}
    if "shift_id" not in users_cols:
        session.execute(text("ALTER TABLE users ADD COLUMN shift_id INTEGER"))
        session.commit()

    attendance_cols = {c["name"] for c in inspect(db_engine).get_columns("attendance_log")}
    if "is_processed" not in attendance_cols:
        session.execute(text("ALTER TABLE attendance_log ADD COLUMN is_processed BOOLEAN"))
        session.commit()

    terminal_cols = {c["name"] for c in inspect(db_engine).get_columns("device_terminal")}
    if "connection_params" not in terminal_cols:
        column_type = "JSONB" if db_engine.url.get_backend_name() == "postgresql" else "JSON"
        session.execute(text(f"ALTER TABLE device_terminal ADD COLUMN connection_params {column_type}"))
        session.commit()
    terminal_additions = [
        ("pull_schedule_enabled", "BOOLEAN DEFAULT FALSE"),
        ("pull_schedule_mode", "VARCHAR(20) DEFAULT 'interval'"),
        ("pull_interval_minutes", "INTEGER"),
        ("pull_schedule_weekdays", "JSONB" if db_engine.url.get_backend_name() == "postgresql" else "JSON"),
        ("pull_schedule_time", "TIME"),
        ("pull_schedule_start_date", "DATE"),
        ("pull_schedule_end_date", "DATE"),
        ("pull_window_start", "TIME"),
        ("pull_window_end", "TIME"),
        ("next_pull_at", "TIMESTAMP"),
        ("last_pull_status", "VARCHAR(20)"),
        ("last_pull_error", "VARCHAR(500)"),
    ]
    for column_name, column_type in terminal_additions:
        if column_name not in terminal_cols:
            session.execute(text(f"ALTER TABLE device_terminal ADD COLUMN {column_name} {column_type}"))
            session.commit()

    pa_cols = {c["name"] for c in inspect(db_engine).get_columns("processed_attendance")}
    for col_def in [
        ("previous_status", "VARCHAR(20)"),
        ("pending_first_in", "TIME"),
        ("pending_last_out", "TIME"),
        ("pending_justification", "VARCHAR"),
        ("requested_by", "VARCHAR"),
    ]:
        if col_def[0] not in pa_cols:
            session.execute(text(f"ALTER TABLE processed_attendance ADD COLUMN {col_def[0]} {col_def[1]}"))
            session.commit()

    session.execute(text("UPDATE auth_user SET role = 'viewer' WHERE role IS NULL OR role = ''"))
    session.execute(text("UPDATE auth_user SET must_change_password = FALSE WHERE must_change_password IS NULL"))
    session.execute(text("UPDATE auth_user SET is_active = TRUE WHERE is_active IS NULL"))
    session.execute(text("UPDATE auth_user SET token_version = 0 WHERE token_version IS NULL"))
    session.execute(text("UPDATE attendance_log SET is_processed = FALSE WHERE is_processed IS NULL"))
    session.execute(text(
        "DELETE FROM attendance_log "
        "WHERE raw_identifier = '' AND date IS NULL AND time IS NULL AND mark_type IS NULL"
    ))
    session.commit()

    # Password inicial del admin: configurable por entorno para deploys (sin
    # default hardcodeado en producción). Siempre se exige cambiarlo al login.
    initial_admin_password = os.environ.get("SRTIME_ADMIN_PASSWORD")
    admin = session.query(AuthUser).filter_by(username="admin").first()
    if not admin:
        if defer_admin_setup:
            logger.info("Admin creation deferred until web setup")
            session.close()
            return
        if not initial_admin_password:
            if os.getenv("SRTIME_DEFER_ADMIN_SETUP", "").lower() in ("1", "true", "yes", "on"):
                logger.info("Admin creation deferred until web setup")
                session.close()
                return
            raise RuntimeError("SRTIME_ADMIN_PASSWORD is required for non-web database bootstrap")
        admin = AuthUser(
            username="admin",
            password_hash=hash_password(initial_admin_password),
            role="root",
            must_change_password=True,
        )
        session.add(admin)
        session.commit()
    else:
        changed = False
        admin_hash = str(getattr(admin, "password_hash", "") or "")
        if not admin_hash:
            if not initial_admin_password:
                raise RuntimeError("SRTIME_ADMIN_PASSWORD is required to repair the admin account")
            setattr(admin, "password_hash", hash_password(initial_admin_password))
            changed = True
        role_value = getattr(admin, "role", None)
        if not role_value or role_value == "admin":
            setattr(admin, "role", "root")
            changed = True
        must_change = getattr(admin, "must_change_password", None)
        if must_change is None:
            setattr(admin, "must_change_password", True)
            changed = True
        else:
            admin_username = str(getattr(admin, "username", ""))
            default_password_still_set = bool(admin_hash) and verify_password("admin", admin_hash)
            if admin_username == "admin" and default_password_still_set:
                setattr(admin, "must_change_password", True)
                changed = True
        if changed:
            session.commit()

    # Safety net: always keep at least one root account.
    root_count = session.query(AuthUser).filter_by(role="root").count()
    if root_count == 0:
        admin = session.query(AuthUser).filter_by(username="admin").first()
        if admin:
            setattr(admin, "role", "root")
            session.commit()

    logger.info("Database initialization complete")
    session.close()
