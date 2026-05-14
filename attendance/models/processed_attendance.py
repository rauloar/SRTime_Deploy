from sqlalchemy import Column, Integer, String, Date, Time, Float, ForeignKey, UniqueConstraint
from core.database import Base

class ProcessedAttendance(Base):
    __tablename__ = "processed_attendance"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)

    first_in = Column(Time, nullable=True)
    last_out = Column(Time, nullable=True)

    total_hours = Column(Float, default=0.0)
    tardiness_minutes = Column(Integer, default=0)
    early_departure_minutes = Column(Integer, default=0)
    overtime_minutes = Column(Integer, default=0)
    # Statuses: OK, INCOMPLETO, JUSTIFICADO, FERIADO, PENDIENTE
    status = Column(String(20), default="OK")
    justification = Column(String, nullable=True)

    # Justification workflow: supervisor requests → root approves/rejects
    previous_status = Column(String(20), nullable=True)
    pending_first_in = Column(Time, nullable=True)
    pending_last_out = Column(Time, nullable=True)
    pending_justification = Column(String, nullable=True)
    requested_by = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("employee_id", "date"),
    )
