from datetime import date, time
from typing import Iterator, Tuple

from services.addons.base_driver import BiometricDriver, TerminalCheckError
from services.addons.sundial.protocol import SundialClient


DEFAULT_PORT = 3000
DEFAULT_ADDRESS = "001"
DEFAULT_CONNECTION_TIMEOUT = 5
DEFAULT_CONNECTION_RETRIES = 3
# El contador de pendientes del reloj no siempre es confiable: en relojes de
# clientes se vieron 65535, 85125 y 99974-99997 (contador negativo) mientras
# las lecturas traían unos cientos o miles. Por encima de este valor se informa
# como dato no confiable. La descarga no depende del contador: lee hasta que el
# reloj avisa que no hay más.
PLAUSIBLE_PENDING_MAX = 60000


class SundialDriver(BiometricDriver):
    """Relojes Sundial ERTeckno por red, sin TecknoComm.

    Habla el protocolo serie del reloj a través del módulo Tibbo (TCP 3000).
    El reloj lleva un puntero de lectura y da por entregado cada bloque al
    mandarlo (I5), aunque no llegue la confirmación. SRTime confirma (I3) en
    ``acknowledge_attendance_logs`` después de guardar, y si la ingesta falla
    ``release_attendance_logs`` reposiciona el puntero (I2) en el primer día
    leído: la próxima descarga los vuelve a traer y los ya guardados se cuentan
    como duplicados.
    """

    display_name = "Sundial ERTeckno"

    def __init__(self):
        self.client = None
        self._params = None
        self._status = None
        self._records = None

    @staticmethod
    def _address(params: dict) -> str:
        raw = str(params.get("address") or DEFAULT_ADDRESS).strip()
        if not raw.isdigit() or not 1 <= int(raw) <= 999:
            raise ValueError("El número de terminal debe estar entre 1 y 999")
        return f"{int(raw):03d}"

    def connect(self, params: dict):
        self._params = dict(params)
        ip = str(params.get("ip") or "").strip()
        port = DEFAULT_PORT
        timeout = DEFAULT_CONNECTION_TIMEOUT
        retries = DEFAULT_CONNECTION_RETRIES
        try:
            if not ip:
                raise ValueError("La dirección IP del módulo Tibbo es obligatoria")
            port = int(params.get("port") or DEFAULT_PORT)
            address = self._address(params)
            timeout = int(params.get("timeout") or DEFAULT_CONNECTION_TIMEOUT)
            retries = max(1, int(params.get("retries") or DEFAULT_CONNECTION_RETRIES))
            last_error = None
            tibbo_answered = False
            for _attempt in range(retries):
                try:
                    self.client = SundialClient(ip, port, address, timeout=timeout)
                    self.client.connect()
                    return
                except Exception as exc:
                    last_error = exc
                    # Con el socket abierto, la red y el módulo Tibbo funcionan:
                    # lo que no contesta es el reloj (apagado, cable serie,
                    # número de terminal o configuración del puerto serie).
                    tibbo_answered = tibbo_answered or bool(self.client and self.client.sock)
                    self.disconnect()
            if tibbo_answered:
                raise TerminalCheckError(
                    f"Chequear terminal: el módulo Tibbo de {ip}:{port} responde, "
                    f"pero el reloj (terminal {address}) no contesta."
                ) from last_error
            raise last_error or RuntimeError("El reloj no respondió")
        except TerminalCheckError:
            raise
        except Exception as e:
            raise ConnectionError(
                f"Error al conectar con Sundial en {ip}:{port} "
                f"tras {retries} intentos de {timeout}s - {str(e)}"
            ) from e

    def _require_client(self) -> SundialClient:
        if not self.client:
            raise Exception("No hay conexión activa con el dispositivo.")
        return self.client

    def _load_status(self):
        if self._status is None:
            self._status = self._require_client().status()
        return self._status

    def _load_records(self):
        if self._records is None:
            # Con 0 pendientes el reloj no contesta I5 (igual que TecknoComm).
            pending = self._load_status().pending
            self._records = []
            if pending != 0:
                # Se acumula bloque a bloque: si la lectura se corta, lo ya
                # recibido (que el reloj dio por entregado) queda para
                # release_attendance_logs.
                for block in self._require_client().iter_record_blocks():
                    self._records.extend(block)
        return self._records

    @staticmethod
    def _plausible_pending(pending):
        return pending is not None and 0 <= pending <= PLAUSIBLE_PENDING_MAX

    def get_attendance_log_count(self):
        pending = self._load_status().pending
        return pending if self._plausible_pending(pending) else None

    def get_attendance_logs(self) -> Iterator[Tuple[str, object, time, int, str]]:
        terminal = int(self.client.address)
        for record in self._load_records():
            # Mismo contrato que una línea TM-MR001: flags = función(2) +
            # terminal(3) + "00", y Entrada/Salida desde el estado del punch.
            flags = f"{record.function:02d}{terminal:03d}00"
            yield record.card, record.day, time(record.hour, record.minute), record.state, flags

    def acknowledge_attendance_logs(self) -> None:
        if self._records:
            # Ya están guardados: si I3 falla no hay nada que devolver.
            self._records = []
            self._require_client().confirm_read()

    def release_attendance_logs(self):
        """I2 al primer día leído y no guardado. Devuelve esa fecha (o None)."""
        if not self._records:
            return None
        since = min(record.day for record in self._records)
        try:
            self._require_client().set_pointer(since)
        except Exception:
            # La lectura pudo haber cortado la conexión: una nueva para I2.
            params = self._params
            self.disconnect()
            self.connect(params)
            self._require_client().set_pointer(since)
        self._records = []
        return since

    def test_connection(self, params: dict) -> dict:
        from core.timezone import local_now

        self.connect(params)
        try:
            status = self._load_status()
            result = {
                "status": "ok",
                "address": self.client.address,
                "time": str(status.clock) if status.clock else None,
                "pending_records": status.pending,
            }
            if not self._plausible_pending(status.pending):
                shown = "sin dato" if status.pending is None else status.pending
                result["pending_records"] = (
                    f"Sin dato confiable ({shown}). Si la descarga trae marcas viejas, "
                    "usar «Volver a bajar registros desde…»"
                )
            if status.clock:
                drift = status.clock - local_now().replace(tzinfo=None)
                result["clock_drift"] = f"{round(drift.total_seconds()):+d} s"
            return result
        finally:
            self.disconnect()

    def sync_time(self, params: dict) -> bool:
        from core.timezone import local_now

        self.connect(params)
        try:
            self._require_client().set_datetime(local_now().replace(tzinfo=None))
            return True
        finally:
            self.disconnect()

    def set_attendance_pointer(self, params: dict, since: date) -> bool:
        self.connect(params)
        try:
            self._require_client().set_pointer(since)
            return True
        finally:
            self.disconnect()

    def disconnect(self):
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
        self._status = None
        self._records = None
