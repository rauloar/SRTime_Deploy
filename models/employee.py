from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    identifier = Column(String(15), unique=True, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    is_active = Column(Boolean, default=True)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=True)