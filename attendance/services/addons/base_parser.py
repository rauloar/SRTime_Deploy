from abc import ABC, abstractmethod
from typing import Tuple, Optional
from datetime import date, time

class AttendanceParser(ABC):
    """
    Clase base para todos los parsers de terminales biométricas.
    """
    display_name = "Base Parser"
    
    @abstractmethod
    def parse_line(self, line: str) -> Optional[Tuple[str, date, time, int, str]]:
        """
        Analiza una línea de texto del archivo fuente y retorna los datos extraídos.
        
        Args:
            line: Una línea completa de texto del archivo.
            
        Returns:
            Una tupla contenedor:
            (identifier, date, time, mark_type, flags)
            
            - identifier: str, el ID del empleado (generalmente código)
            - date: datetime.date, fecha del movimiento
            - time: datetime.time, hora del movimiento
            - mark_type: int, tipo de marca (0 entrada, 1 salida por ejemplo)
            - flags: str, indicadores adicionales (sucursal, dispositivo, etc.)
            
            Si la línea es inválida, se debe retornar None para ignorarla.
        """
        pass
