from sqlalchemy import Column, Integer, String, Time, Boolean
from core.database import Base

class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    expected_in = Column(Time, nullable=False)
    expected_out = Column(Time, nullable=False)
    grace_period_minutes = Column(Integer, default=15)
    is_overnight_shift = Column(Boolean, default=False)  # True si el turno cruza medianoche
    break_duration_minutes = Column(Integer, default=0)   # Duración del descanso a deducir
