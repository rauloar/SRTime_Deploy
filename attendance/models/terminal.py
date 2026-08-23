from sqlalchemy import JSON, Column, Integer, String, Boolean, DateTime, Time
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
    # La agenda pertenece a la terminal, no a los movimientos crudos.  Mantenerla
    # aquí evita una segunda fuente de verdad para la configuración del equipo.
    pull_schedule_enabled = Column(Boolean, default=False, nullable=False)
    pull_interval_minutes = Column(Integer, nullable=True)
    pull_window_start = Column(Time, nullable=True)
    pull_window_end = Column(Time, nullable=True)
    next_pull_at = Column(DateTime, nullable=True)
    last_pull_status = Column(String(20), nullable=True)
    last_pull_error = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=func.now())
