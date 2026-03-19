from sqlalchemy import Column, Integer, String, Time
from core.database import Base

class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    expected_in = Column(Time, nullable=False)
    expected_out = Column(Time, nullable=False)
    grace_period_minutes = Column(Integer, default=15)
