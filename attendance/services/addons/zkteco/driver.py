from typing import Iterator, Tuple
from datetime import date, time
from services.addons.base_driver import BiometricDriver


class ZKTecoDriver(BiometricDriver):
    display_name = "ZKTeco"

    connection_fields = [
        {"name": "ip", "label": "Dirección IP", "type": "text", "default": "192.168.1.201"},
        {"name": "port", "label": "Puerto", "type": "number", "default": "4370"},
        {"name": "password", "label": "Contraseña Com (0=Sin Clave)", "type": "text", "default": "0"},
    ]

    def __init__(self):
        self.zk = None
        self.conn = None

    def connect(self, params: dict):
        try:
            from zk import ZK

            ip = params.get("ip", "192.168.1.201")
            port = int(params.get("port", 4370))
            password = int(params.get("password", 0))

            self.zk = ZK(ip, port=port, timeout=5, password=password, force_udp=False, ommit_ping=False)
            self.conn = self.zk.connect()
            self.conn.disable_device()
        except Exception as e:
            raise Exception(f"Error al conectar con ZKTeco en {ip}:{port} - {str(e)}")

    def get_attendance_logs(self) -> Iterator[Tuple[str, date, time, int, str]]:
        if not self.conn:
            raise Exception("No hay conexión activa con el dispositivo.")

        try:
            attendances = self.conn.get_attendance()
            for att in attendances:
                identifier = str(att.user_id).strip().zfill(15)
                dt = att.timestamp
                if not dt: continue
                d = dt.date()
                t = dt.time()

                mark_type = int(att.status)
                if mark_type not in (0, 1):
                    pass

                flags = "0100100"

                yield identifier, d, t, mark_type, flags
        except Exception as e:
            raise Exception(f"Error al leer asistencias: {str(e)}")

    def test_connection(self, params: dict) -> dict:
        self.connect(params)
        try:
            name = self.conn.get_device_name()
            mac = self.conn.get_mac()
            t = self.conn.get_time()
            return {"status": "ok", "name": name, "mac": mac, "time": str(t)}
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
                self.conn.enable_device()
                self.conn.disconnect()
            except:
                pass
            self.conn = None
