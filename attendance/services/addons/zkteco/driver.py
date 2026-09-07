from typing import Iterator, Tuple
from datetime import date, time
from services.addons.base_driver import BiometricDriver


DEFAULT_CONNECTION_TIMEOUT = 5
DEFAULT_CONNECTION_RETRIES = 3


class ZKTecoDriver(BiometricDriver):
    display_name = "ZKTeco"

    connection_fields = [
        {"name": "ip", "label": "Dirección IP", "type": "text", "default": "", "required": True},
        {"name": "port", "label": "Puerto", "type": "number", "default": "4370"},
    ]

    def __init__(self):
        self.zk = None
        self.conn = None
        self._attendance_cache = None

    def connect(self, params: dict):
        ip = ""
        port = 4370
        timeout = DEFAULT_CONNECTION_TIMEOUT
        retries = DEFAULT_CONNECTION_RETRIES
        last_error = None
        try:
            from zk import ZK

            ip = str(params.get("ip") or "").strip()
            if not ip:
                raise ValueError("La dirección IP de la terminal es obligatoria")
            port = int(params.get("port", 4370))
            timeout = int(params.get("timeout") or DEFAULT_CONNECTION_TIMEOUT)
            retries = max(1, int(params.get("retries") or DEFAULT_CONNECTION_RETRIES))
            # Mantener el contrato pyzk validado con el dispositivo
            # (ZK('IP', port=4370)), agregando sólo timeout configurable para
            # que la UI no quede bloqueada 60s cuando la terminal/red no responde.
            for attempt in range(1, retries + 1):
                try:
                    self.zk = ZK(ip, port=port, timeout=timeout)
                    self.conn = self.zk.connect()
                    return
                except Exception as exc:
                    last_error = exc
                    self.disconnect()
            raise last_error or RuntimeError("La terminal no respondió")
        except Exception as e:
            raise ConnectionError(
                f"Error al conectar con ZKTeco en {ip}:{port} "
                f"tras {retries} intentos de {timeout}s - {str(e)}"
            ) from e

    def _load_attendance(self):
        if not self.conn:
            raise Exception("No hay conexión activa con el dispositivo.")
        try:
            if self._attendance_cache is None:
                self._attendance_cache = list(self.conn.get_attendance())
            return self._attendance_cache
        except Exception as e:
            raise Exception(f"Error al leer asistencias: {str(e)}") from e

    def get_attendance_log_count(self):
        return len(self._load_attendance())

    def get_attendance_logs(self) -> Iterator[Tuple[str, date, time, int, str]]:
        try:
            for att in self._load_attendance():
                identifier = str(att.user_id).strip().zfill(15)
                dt = att.timestamp
                if not dt: continue
                d = dt.date()
                t = dt.time()

                mark_type = self._mark_type_from_punch(getattr(att, "punch", 0))
                status = self._safe_int(getattr(att, "status", 0), 0)

                # SRTime conserva 7 chars de metadata como el formato base.
                # ZKTeco separa ``status`` (modo/estado de verificación) de
                # ``punch`` (tipo de marcación). La dirección Entrada/Salida
                # nunca debe salir de ``status``.
                flags = f"ZK{status:05d}"[-7:]

                yield identifier, d, t, mark_type, flags
        except Exception as e:
            raise Exception(f"Error al normalizar asistencias: {str(e)}") from e

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _mark_type_from_punch(cls, punch) -> int:
        """Normaliza el punch ZKTeco al contrato SRTime/TM-MR001.

        Valores comunes de firmware ZK:
        0 Check-In, 1 Check-Out, 2 Break-Out, 3 Break-In,
        4 Overtime-In, 5 Overtime-Out.
        """
        value = cls._safe_int(punch, 0)
        if value in {1, 2, 5}:
            return 1
        return 0

    def get_terminal_users(self) -> list[dict]:
        if not self.conn:
            raise Exception("No hay conexión activa con el dispositivo.")
        try:
            return [
                {
                    "uid": int(user.uid),
                    "user_id": str(user.user_id),
                    "name": str(user.name),
                    "privilege": int(user.privilege),
                    "password": str(user.password),
                    "group_id": str(user.group_id),
                    "card": int(user.card),
                }
                for user in self.conn.get_users()
            ]
        except Exception as e:
            raise Exception(f"Error al leer usuarios de ZKTeco: {str(e)}") from e

    def update_terminal_user_name(self, user: dict, name: str) -> None:
        self.update_terminal_user_profile(user, name, int(user["privilege"]))

    def update_terminal_user_profile(self, user: dict, name: str, privilege: int) -> None:
        if not self.conn:
            raise Exception("No hay conexión activa con el dispositivo.")
        # ``set_user`` actualiza por UID. Reenviar todos los atributos evita
        # alterar contraseña, grupo, tarjeta, UID o user_id del reloj.
        self.conn.set_user(
            uid=int(user["uid"]),
            user_id=str(user["user_id"]),
            name=name,
            privilege=int(privilege),
            password=str(user.get("password") or ""),
            group_id=str(user.get("group_id") or ""),
            card=int(user.get("card") or 0),
        )

    def get_terminal_user_name_max_bytes(self):
        if not self.conn:
            raise Exception("No hay conexión activa con el dispositivo.")
        # PyZK identifica perfiles ZK6 con paquetes de 28 bytes (nombre de 8)
        # y ZK8 con paquetes de 72 bytes (nombre de 24).
        packet_size = getattr(self.conn, "user_packet_size", None)
        if packet_size == 28:
            return 8
        if packet_size == 72:
            return 24
        return None

    def test_connection(self, params: dict) -> dict:
        self.connect(params)
        try:
            name = self.conn.get_device_name()
            mac = self.conn.get_mac()
            serial_number = self.conn.get_serialnumber()
            firmware = self.conn.get_firmware_version()
            t = self.conn.get_time()
            return {
                "status": "ok",
                "name": name,
                "mac": mac,
                "serial_number": serial_number,
                "firmware": firmware,
                "time": str(t),
            }
        finally:
            self.disconnect()

    def sync_time(self, params: dict) -> bool:
        from core.timezone import local_now

        self.connect(params)
        try:
            self.conn.set_time(local_now().replace(tzinfo=None))
            return True
        finally:
            self.disconnect()

    def clear_attendance_logs(self) -> bool:
        if not self.conn:
            raise Exception("No hay conexión activa con el dispositivo.")
        self.conn.clear_attendance()
        self._attendance_cache = None
        return True

    def disconnect(self):
        if self.conn:
            try:
                self.conn.disconnect()
            except Exception:
                pass
            self.conn = None
        self._attendance_cache = None
