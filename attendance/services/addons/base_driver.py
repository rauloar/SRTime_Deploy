from typing import Optional, Tuple, Iterator
from datetime import date, time

class TerminalCheckError(ConnectionError):
    """Falla diagnosticada por el driver, con un mensaje pensado para el operador.

    La API y el Desktop lo muestran tal cual (por ejemplo "Chequear terminal: ...").
    Cualquier otra excepción se muestra como falta de conectividad genérica y el
    detalle técnico queda sólo en el log.
    """


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

    def acknowledge_attendance_logs(self) -> None:
        """Confirma al equipo que los registros leídos ya quedaron guardados.

        Se llama sólo después de que la ingesta hizo commit. Equipos que llevan
        un puntero de lectura lo avanzan acá; si la confirmación no
        llega, la próxima descarga repite registros que se detectan como
        duplicados. Default: no hace nada.
        """
        return None

    def test_connection(self, params: dict) -> dict:
        """Prueba la conexión y devuelve metadatos como mac, nombre, hora, etc."""
        return {"status": "unsupported"}

    def sync_time(self, params: dict) -> bool:
        """Sincroniza la hora y fecha del dispositivo con la actual."""
        return False

    def set_attendance_pointer(self, params: dict, since: date) -> bool:
        """Reposiciona la lectura del equipo para volver a entregar desde ``since``.

        Sólo para equipos que llevan puntero de lectura (capability
        ``attendance_pointer``). La próxima descarga trae de nuevo esos
        registros; los ya guardados se cuentan como duplicados.
        """
        raise NotImplementedError("El driver no admite volver a bajar registros desde una fecha")

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
