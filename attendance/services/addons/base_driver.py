from typing import Optional, Tuple, Iterator
from datetime import date, time

class BiometricDriver:
    """
    Clase base para Addons que se comunican directamente con dispositivos biométricos a través de la red (no archivos).
    """
    display_name = "Controlador de Dispositivo"
    
    # Define la UI dinámica para las credenciales
    # Ejemplo: [{"name": "ip", "label": "IP del Reloj", "default": "", "required": True}]
    connection_fields = []

    def connect(self, params: dict):
        pass

    def get_attendance_logs(self) -> Iterator[Tuple[str, date, time, int, str]]:
        pass

    def get_attendance_log_count(self) -> Optional[int]:
        """Cantidad de registros disponibles, si el equipo la puede informar.

        Se usa exclusivamente para progreso. ``None`` significa que el driver
        no puede conocer el total sin recorrer el origen.
        """
        return None

    def test_connection(self, params: dict) -> dict:
        """Prueba la conexión y devuelve metadatos como mac, nombre, hora, etc."""
        return {"status": "unsupported"}

    def sync_time(self, params: dict) -> bool:
        """Sincroniza la hora y fecha del dispositivo con la actual."""
        return False

    def clear_attendance_logs(self) -> bool:
        """Borra la memoria de marcaciones del equipo, si el driver lo soporta."""
        raise NotImplementedError("El driver no admite borrar la memoria de marcaciones")

    def get_terminal_users(self) -> list[dict]:
        """Lista usuarios del equipo. Add-ons sin gestión devuelven error."""
        raise NotImplementedError("El driver no admite gestión de usuarios")

    def update_terminal_user_name(self, user: dict, name: str) -> None:
        """Actualiza sólo el nombre conservando el resto del perfil del reloj."""
        raise NotImplementedError("El driver no admite gestión de usuarios")

    def update_terminal_user_profile(self, user: dict, name: str, privilege: int) -> None:
        """Actualiza nombre y privilegio conservando UID, user_id y credenciales."""
        self.update_terminal_user_name(user, name)

    def get_terminal_user_name_max_bytes(self) -> Optional[int]:
        """Límite de nombre del equipo, si el protocolo lo informa."""
        return None

    def disconnect(self):
        pass
