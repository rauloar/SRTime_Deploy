from sqlalchemy import Column, Integer, String, Date, Boolean
from core.database import Base


class Holiday(Base):
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True)
    name = Column(String, nullable=False)
    is_recurring = Column(Boolean, default=False)
