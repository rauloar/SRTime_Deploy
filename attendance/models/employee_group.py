from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from core.database import Base


class EmployeeGroup(Base):
    __tablename__ = "employee_group"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String, nullable=True)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
