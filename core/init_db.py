from core.database import engine, Base
from models import user, attendance
from models.employee import User
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from core.security import hash_password, verify_password
from models.user import AuthUser
from models.shift import Shift
from models.processed_attendance import ProcessedAttendance

def init_database():
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)

    # Backward-compatible bootstrap for existing databases.
    cols = {c["name"] for c in inspect(engine).get_columns("auth_user")}
    if "role" not in cols:
        session.execute(text("ALTER TABLE auth_user ADD COLUMN role VARCHAR(20)"))
        session.commit()
    if "must_change_password" not in cols:
        session.execute(text("ALTER TABLE auth_user ADD COLUMN must_change_password BOOLEAN"))
        session.commit()

    session.execute(text("UPDATE auth_user SET role = 'viewer' WHERE role IS NULL OR role = ''"))
    session.execute(text("UPDATE auth_user SET must_change_password = FALSE WHERE must_change_password IS NULL"))
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
            admin_hash = str(getattr(admin, "password_hash", ""))
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

    session.close()