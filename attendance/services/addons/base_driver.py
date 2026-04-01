from typing import Optional, Tuple, Iterator
from datetime import date, time

class BiometricDriver:
    """
    Clase base para Addons que se comunican directamente con dispositivos biométricos a través de la red (no archivos).
    """
    display_name = "Controlador de Dispositivo"
    
    # Define la UI dinámica para las credenciales
    # Ejemplo: [{"name": "ip", "label": "IP del Reloj", "default": "192.168.1.201"}]
    connection_fields = []

    def connect(self, params: dict):
        pass

    def get_attendance_logs(self) -> Iterator[Tuple[str, date, time, int, str]]:
        pass

    def test_connection(self, params: dict) -> dict:
        """Prueba la conexión y devuelve metadatos como mac, nombre, hora, etc."""
        return {"status": "unsupported"}

    def sync_time(self, params: dict) -> bool:
        """Sincroniza la hora y fecha del dispositivo con la actual."""
        return False

    def disconnect(self):
        pass
