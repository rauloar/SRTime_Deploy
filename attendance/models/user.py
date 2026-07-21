from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from core.database import Base

class AuthUser(Base):
    __tablename__ = "auth_user"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String(20), nullable=False, default="viewer")
    must_change_password = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    token_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=func.now())
