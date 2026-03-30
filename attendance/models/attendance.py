from sqlalchemy import Column, Integer, String, Date, Time, DateTime, ForeignKey, UniqueConstraint, Boolean
from datetime import datetime
from core.database import Base

class AttendanceLog(Base):
    __tablename__ = "attendance_log"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("users.id"))
    raw_identifier = Column(String(15))
    date = Column(Date)
    time = Column(Time)
    mark_type = Column(Integer)
    flags = Column(String(7))
    source_file = Column(String)
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("raw_identifier", "date", "time", "mark_type"),
    )