"""Driver Sundial contra un reloj simulado (servidor TCP local con el protocolo).

A diferencia de test_sundial_protocol.py no usa sesiones grabadas: el reloj
simulado lleva su propio puntero y registra qué comandos recibió, para verificar
el contrato con SRTime (I3 sólo después de guardar, sin I5 con 0 pendientes).
"""

import socket
import threading
from datetime import date, datetime, time

import pytest

from models.attendance import AttendanceLog
from models.terminal import DeviceTerminal
from services import terminals
from services.addons import get_addon_info
from services.addons.sundial import protocol
from services.addons.sundial.driver import SundialDriver
from services.addons.sundial.parser import SundialParser


DAY = date(2026, 10, 30)
RECORDS = [
    # tarjeta, hora, minuto, estado, función
    ("000000000010034", 6, 14, 0, 0),
    ("000000000010034", 14, 2, 1, 0),
    ("000000000020001", 7, 59, 0, 3),
]


class FakeSundialClock:
    """Reloj Sundial mínimo: conexión, estado, lectura por bloques, I3 y hora."""

    def __init__(self, address="001", records=RECORDS):
        self.address = address
        self.pending = list(records)
        self.delivered = False
        self.pointer = None
        self.commands: list[bytes] = []
        self.clock = datetime(2026, 10, 30, 19, 30, 0)
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen()
        self.port = self.server.getsockname()[1]
        self._stop = False
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def close(self):
        self._stop = True
        self.server.close()

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                self._session(conn)

    def _reply(self, conn, body: bytes):
        conn.sendall(protocol.build_frame(self.address, body))

    def _session(self, conn):
        buf = b""
        while True:
            try:
                chunk = conn.recv(4096)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while (found := protocol.extract_frame(buf)):
                body, _raw, buf = found
                self._handle(conn, body)

    def _handle(self, conn, body: bytes):
        if body == b"^0":
            self.commands.append(b"^0")
            self._reply(conn, b"^B")
            return
        seq, cmd = body[:1], body[2:]
        self.commands.append(cmd[:2])
        if cmd == b"I4":
            self._reply(conn, seq + b"Bi10" + self.clock.strftime("%d%m%y%H%M%S").encode()
                        + f"{len(self.pending):05d}".encode() + b"000")
        elif cmd == b"I5":
            if not self.pending:
                return  # el reloj real no contesta I5 sin pendientes
            if self.delivered:
                self._reply(conn, seq + b"Bc30")
                return
            data = b"".join(
                card.encode() + bytes([h + 0x21, m + 0x21, 0x40 + state, func + 0x21])
                for card, h, m, state, func in self.pending
            )
            self.delivered = True
            self._reply(conn, seq + b"Bi00" + DAY.strftime("%d%m%y").encode() + data)
        elif cmd == b"I3":
            if self.delivered:
                self.pending, self.delivered = [], False
            self._reply(conn, seq + b"Bc10")
        elif cmd.startswith(b"H0"):
            self.clock = datetime.strptime(cmd[2:].decode(), "%d%m%y%H%M%S")
            self._reply(conn, seq + b"Bc10")
        elif cmd.startswith(b"I2"):
            self.pointer = datetime.strptime(cmd[2:].decode(), "%d%m%Y").date()
            self._reply(conn, seq + b"Bc10")


@pytest.fixture
def clock():
    fake = FakeSundialClock()
    yield fake
    fake.close()


def _terminal(session, clock) -> DeviceTerminal:
    terminal = DeviceTerminal(
        name="Recepción",
        driver_name="Sundial ERTeckno",
        ip="127.0.0.1",
        port=clock.port,
        connection_params={"ip": "127.0.0.1", "port": str(clock.port), "address": "1", "timeout": "2"},
    )
    session.add(terminal)
    session.commit()
    return terminal


def test_manifest_exposes_driver_and_keeps_file_import():
    info = get_addon_info("Sundial ERTeckno")

    assert info["is_driver"] is True and info["is_parser"] is True
    assert info["driver_class"] is SundialDriver
    assert info["parser_class"] is SundialParser
    assert [field["name"] for field in info["connection_fields"]] == ["ip", "port", "address", "timeout"]
    capabilities = info["manifest"]["capabilities"]
    assert capabilities["attendance_count"] is True
    assert not capabilities["terminal_users"]
    assert not capabilities["clear_attendance_memory"]


def test_test_connection_reports_clock_and_pending(test_db, clock):
    result = terminals.test_connection(_terminal(test_db, clock))

    assert result["status"] == "ok"
    assert result["address"] == "001"
    assert result["pending_records"] == 3
    assert result["time"] == "2026-10-30 19:30:00"
    labels = [item["label"] for item in result["details"]]
    assert labels == ["Número de terminal", "Hora del reloj", "Desvío de hora", "Registros pendientes"]
    # Probar la conexión no lee ni confirma registros.
    assert b"I5" not in clock.commands and b"I3" not in clock.commands


def test_pull_ingests_then_confirms_pointer(test_db, clock):
    terminal = _terminal(test_db, clock)

    nuevos, duplicados, total, _logs = terminals.pull_logs(terminal, test_db)

    assert (nuevos, duplicados, total) == (3, 0, 3)
    assert clock.commands[-1] == b"I3"
    assert clock.pending == []
    logs = test_db.query(AttendanceLog).order_by(AttendanceLog.time).all()
    assert [(log.raw_identifier, log.time, log.mark_type, log.flags) for log in logs] == [
        ("000000000010034", time(6, 14), 0, "0000100"),
        ("000000000020001", time(7, 59), 0, "0300100"),
        ("000000000010034", time(14, 2), 1, "0000100"),
    ]
    assert terminal.last_sync is not None


def test_pull_without_pending_does_not_request_records(test_db, clock):
    clock.pending = []

    result = terminals.pull_logs(_terminal(test_db, clock), test_db)

    assert result[:3] == (0, 0, 0)
    assert b"I5" not in clock.commands and b"I3" not in clock.commands


def test_failed_ingest_leaves_pointer_untouched(test_db, clock, monkeypatch):
    import services.importer_service as importer

    def broken_ingest(**_kwargs):
        raise RuntimeError("base no disponible")

    monkeypatch.setattr(importer, "_ingest_rows", broken_ingest)

    with pytest.raises(RuntimeError):
        terminals.pull_logs(_terminal(test_db, clock), test_db)

    # Sin I3 el reloj conserva las marcas para la próxima descarga.
    assert b"I3" not in clock.commands
    assert len(clock.pending) == 3


def test_network_rows_match_tm_mr001_file_rows(clock):
    """Una marca bajada por red es idéntica a la misma marca importada por archivo."""
    driver = SundialDriver()
    driver.connect({"ip": "127.0.0.1", "port": clock.port, "address": "1", "timeout": 2})
    try:
        network_rows = list(driver.get_attendance_logs())
    finally:
        driver.disconnect()

    parser = SundialParser()
    file_rows = [
        parser.parse_line(protocol.Record(card, DAY, h, m, state, func).to_tm_line(1))
        for card, h, m, state, func in RECORDS
    ]
    assert network_rows == file_rows


def test_sync_time_sets_clock(test_db, clock):
    assert terminals.sync_time(_terminal(test_db, clock)) is True
    assert any(cmd == b"H0" for cmd in clock.commands)
    assert clock.clock != datetime(2026, 10, 30, 19, 30, 0)


def test_invalid_terminal_number_is_rejected():
    with pytest.raises(ConnectionError, match="número de terminal"):
        SundialDriver().connect({"ip": "127.0.0.1", "address": "1000", "retries": 1})


def test_attendance_pointer_sends_requested_date(test_db, clock):
    assert terminals.set_attendance_pointer(_terminal(test_db, clock), date(2026, 10, 1)) is True
    assert clock.pointer == date(2026, 10, 1)
    # Reposicionar no lee ni confirma registros.
    assert b"I5" not in clock.commands and b"I3" not in clock.commands


def test_attendance_pointer_rejects_future_date(test_db, clock):
    with pytest.raises(terminals.TerminalOperationError, match="posterior a hoy"):
        terminals.set_attendance_pointer(_terminal(test_db, clock), date(2999, 1, 1))
    assert clock.pointer is None


def test_attendance_pointer_requires_driver_capability(test_db):
    terminal = DeviceTerminal(name="Reloj", driver_name="ZKTeco", ip="127.0.0.1", port=4370)
    test_db.add(terminal)
    test_db.commit()

    with pytest.raises(terminals.TerminalOperationError, match="no admite"):
        terminals.set_attendance_pointer(terminal, date(2026, 10, 1))


def test_protocol_errors_are_runtime_errors():
    """El router convierte RuntimeError en 400; un fallo del reloj no debe ser 500."""
    assert issubclass(protocol.SundialError, RuntimeError)
