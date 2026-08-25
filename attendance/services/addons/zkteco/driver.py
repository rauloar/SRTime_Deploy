from typing import Iterator, Tuple
from datetime import date, time
from services.addons.base_driver import BiometricDriver


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
        try:
            from zk import ZK

            ip = str(params.get("ip") or "").strip()
            if not ip:
                raise ValueError("La dirección IP de la terminal es obligatoria")
            port = int(params.get("port", 4370))
            # Mantener exactamente el formato de conexión validado con el
            # dispositivo: ZK('IP', port=4370). PyZK aplica sus defaults.
            self.zk = ZK(ip, port=port)
            self.conn = self.zk.connect()
        except Exception as e:
            raise Exception(f"Error al conectar con ZKTeco en {ip}:{port} - {str(e)}")

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

                mark_type = int(att.status)
                if mark_type not in (0, 1):
                    mark_type = 0

                flags = "0100100"

                yield identifier, d, t, mark_type, flags
        except Exception as e:
            raise Exception(f"Error al normalizar asistencias: {str(e)}") from e

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
        if not self.conn:
            raise Exception("No hay conexión activa con el dispositivo.")
        # ``set_user`` actualiza por UID. Reenviar todos los atributos evita
        # alterar privilegio, contraseña, grupo, tarjeta o user_id del reloj.
        self.conn.set_user(
            uid=int(user["uid"]),
            user_id=str(user["user_id"]),
            name=name,
            privilege=int(user["privilege"]),
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
        from datetime import datetime
        self.connect(params)
        try:
            self.conn.set_time(datetime.now())
            return True
        finally:
            self.disconnect()

    def disconnect(self):
        if self.conn:
            try:
                self.conn.disconnect()
            except Exception:
                pass
            self.conn = None
        self._attendance_cache = None
