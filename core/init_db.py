from core.database import engine, Base
from models import user, attendance
from models.employee import User
from sqlalchemy.orm import Session
from core.security import hash_password
from models.user import AuthUser
from models.shift import Shift
from models.processed_attendance import ProcessedAttendance

def init_database():
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)

    admin = session.query(AuthUser).filter_by(username="admin").first()
    if not admin:
        admin = AuthUser(
            username="admin",
            password_hash=hash_password("admin")
        )
        session.add(admin)
        session.commit()
    else:
        admin.password_hash = hash_password("admin")
        session.commit()

    session.close()