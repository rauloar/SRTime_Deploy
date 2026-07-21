from sqlalchemy import JSON, Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from core.database import Base


class DeviceTerminal(Base):
    __tablename__ = "device_terminal"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)              # "Recepción", "Planta"
    driver_name = Column(String(100), nullable=False)       # "ZKTeco" (del manifest)
    ip = Column(String(45), nullable=True)                  # Legacy ZKTeco/Hikvision
    port = Column(Integer, default=4370)
    password = Column(String(50), default="0")              # Com password
    connection_params = Column(JSON, nullable=True)         # Configuración genérica del addon
    serial_number = Column(String(100), nullable=True)      # SN del dispositivo (se llena en primer test)
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime, nullable=True)             # Última descarga exitosa
    created_at = Column(DateTime, default=func.now())
