from core.database import engine, Base
from models import user, attendance
from models.employee import User
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from pathlib import Path
from core.security import hash_password, verify_password
from models.user import AuthUser
from models.shift import Shift
from models.processed_attendance import ProcessedAttendance
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

def init_database():
    if not _should_initialize_on_startup():
        logger.debug("Database already initialized, skipping")
        return

    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)

    # Backward-compatible bootstrap for existing databases.
    auth_cols = {c["name"] for c in inspect(engine).get_columns("auth_user")}
    if "role" not in auth_cols:
        session.execute(text("ALTER TABLE auth_user ADD COLUMN role VARCHAR(20)"))
        session.commit()
    if "must_change_password" not in auth_cols:
        session.execute(text("ALTER TABLE auth_user ADD COLUMN must_change_password BOOLEAN"))
        session.commit()

    users_cols = {c["name"] for c in inspect(engine).get_columns("users")}
    if "shift_id" not in users_cols:
        session.execute(text("ALTER TABLE users ADD COLUMN shift_id INTEGER"))
        session.commit()

    attendance_cols = {c["name"] for c in inspect(engine).get_columns("attendance_log")}
    if "is_processed" not in attendance_cols:
        session.execute(text("ALTER TABLE attendance_log ADD COLUMN is_processed BOOLEAN"))
        session.commit()

    session.execute(text("UPDATE auth_user SET role = 'viewer' WHERE role IS NULL OR role = ''"))
    session.execute(text("UPDATE auth_user SET must_change_password = FALSE WHERE must_change_password IS NULL"))
    session.execute(text("UPDATE auth_user SET is_active = TRUE WHERE is_active IS NULL"))
    session.execute(text("UPDATE attendance_log SET is_processed = FALSE WHERE is_processed IS NULL"))
    session.commit()

    admin = session.query(AuthUser).filter_by(username="admin").first()
    if not admin:
        admin = AuthUser(
            username="admin",
            password_hash=hash_password("admin"),
            role="root",
            must_change_password=True,
        )
        session.add(admin)
        session.commit()
    else:
        changed = False
        admin_hash = str(getattr(admin, "password_hash", "") or "")
        if not admin_hash:
            setattr(admin, "password_hash", hash_password("admin"))
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