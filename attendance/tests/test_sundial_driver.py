"""Driver Sundial contra un reloj simulado (servidor TCP local con el protocolo).

A diferencia de test_sundial_protocol.py no usa sesiones grabadas: el reloj
simulado lleva su propio puntero y registra qué comandos recibió, para verificar
el contrato con SRTime (I3 sólo después de guardar, sin I5 con 0 pendientes, I2
al primer día leído si la ingesta falla).

Como los relojes reales, da por entregado lo que manda en I5 aunque no llegue
I3 (visto en el reloj de laboratorio y en el WinSock.Log de un cliente).
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
    """Reloj Sundial mínimo: conexión, estado, lectura por bloques, I3, I2 y hora."""

    def __init__(self, address="001", records=RECORDS):
        self.address = address
        self.memory = list(records)
        self.pending = list(records)
        self.pending_counter = None  # valor de I4 forzado (contador real no confiable)
        self.drop_after_delivery = False  # corta el TCP después de mandar el bloque
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
                try:
                    self._session(conn)
                except ConnectionAbortedError:
                    pass

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
            counter = len(self.pending) if self.pending_counter is None else self.pending_counter
            self._reply(conn, seq + b"Bi10" + self.clock.strftime("%d%m%y%H%M%S").encode()
                        + f"{counter:05d}".encode() + b"000")
        elif cmd == b"I5":
            if self.delivered:
                self._reply(conn, seq + b"Bc30")
                return
            if not self.pending:
                return  # el reloj real no contesta I5 sin pendientes
            data = b"".join(
                card.encode() + bytes([h + 0x21, m + 0x21, 0x40 + state, func + 0x21])
                for card, h, m, state, func in self.pending
            )
            # El reloj real da el bloque por entregado al mandarlo.
            self.pending, self.delivered = [], True
            self._reply(conn, seq + b"Bi00" + DAY.strftime("%d%m%y").encode() + data)
            if self.drop_after_delivery:
                self.drop_after_delivery = False
                raise ConnectionAbortedError
        elif cmd == b"I3":
            self.delivered = False
            self._reply(conn, seq + b"Bc10")
        elif cmd.startswith(b"H0"):
            self.clock = datetime.strptime(cmd[2:].decode(), "%d%m%y%H%M%S")
            self._reply(conn, seq + b"Bc10")
        elif cmd.startswith(b"I2"):
            self.pointer = datetime.strptime(cmd[2:].decode(), "%d%m%Y").date()
            # Vuelve a entregar desde esa fecha (todas las marcas son de DAY).
            self.pending = list(self.memory) if DAY >= self.pointer else []
            self.delivered = False
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


def _broken_ingest(rows, **_kwargs):
    list(rows)  # lee del reloj y después falla al guardar
    raise RuntimeError("base no disponible")


def test_failed_ingest_moves_pointer_back(test_db, clock, monkeypatch):
    import services.importer_service as importer

    monkeypatch.setattr(importer, "_ingest_rows", _broken_ingest)

    with pytest.raises(RuntimeError, match="base no disponible"):
        terminals.pull_logs(_terminal(test_db, clock), test_db)

    # El reloj ya las dio por entregadas: sin I3, pero con I2 al primer día
    # leído vuelven a quedar pendientes para la próxima descarga.
    assert b"I3" not in clock.commands
    assert clock.pointer == DAY
    assert len(clock.pending) == 3


def test_retry_after_failed_ingest_brings_the_records(test_db, clock, monkeypatch):
    import services.importer_service as importer

    terminal = _terminal(test_db, clock)
    original = importer._ingest_rows
    monkeypatch.setattr(importer, "_ingest_rows", _broken_ingest)
    with pytest.raises(RuntimeError):
        terminals.pull_logs(terminal, test_db)
    monkeypatch.setattr(importer, "_ingest_rows", original)

    assert terminals.pull_logs(terminal, test_db)[:3] == (3, 0, 3)
    assert test_db.query(AttendanceLog).count() == 3


def test_connection_cut_mid_read_moves_pointer_back(test_db, clock):
    """Se cortó el TCP después de un bloque: I2 por una conexión nueva."""
    clock.drop_after_delivery = True

    with pytest.raises(Exception):
        terminals.pull_logs(_terminal(test_db, clock), test_db)

    assert clock.pointer == DAY
    assert len(clock.pending) == 3
    assert test_db.query(AttendanceLog).count() == 0


def test_saved_records_are_not_moved_back_when_confirm_fails(clock):
    driver = SundialDriver()
    driver.connect({"ip": "127.0.0.1", "port": clock.port, "address": "1", "timeout": 2})
    try:
        assert len(list(driver.get_attendance_logs())) == 3
        driver.client.close()  # I3 va a fallar
        with pytest.raises(Exception):
            driver.acknowledge_attendance_logs()
        # Ya estaban guardadas: no hay nada que devolver.
        assert driver.release_attendance_logs() is None
    finally:
        driver.disconnect()
    assert clock.pointer is None


@pytest.mark.parametrize("counter", [65535, 85125, 99997])
def test_implausible_pending_counter_is_not_shown_as_a_number(test_db, clock, counter):
    clock.pending_counter = counter

    result = terminals.test_connection(_terminal(test_db, clock))

    assert result["pending_records"].startswith(f"Sin dato confiable ({counter})")
    driver = SundialDriver()
    driver.connect({"ip": "127.0.0.1", "port": clock.port, "address": "1", "timeout": 2})
    try:
        assert driver.get_attendance_log_count() is None  # sin total para el progreso
        assert len(list(driver.get_attendance_logs())) == 3  # se lee igual hasta c30
    finally:
        driver.disconnect()


def test_records_older_than_previous_pull_raise_a_warning(test_db, clock):
    terminal = _terminal(test_db, clock)
    terminal.last_sync = datetime(2026, 11, 20, 10, 0)
    test_db.commit()

    result = terminals.pull_logs(terminal, test_db)
    terminals.record_pull_outcome(terminal, result)

    assert result[:3] == (3, 0, 3)  # se importan igual
    assert len(result.warnings) == 1
    assert "desde el 30/10/2026" in result.warnings[0] and "(20/11/2026)" in result.warnings[0]
    assert terminal.last_pull_status == "warning"
    assert terminal.last_pull_error == result.warnings[0]


@pytest.mark.parametrize("previous", [None, datetime(2026, 10, 30, 18, 0), datetime(2026, 10, 31, 9, 0)])
def test_records_after_previous_pull_do_not_warn(test_db, clock, previous):
    terminal = _terminal(test_db, clock)
    terminal.last_sync = previous
    test_db.commit()

    result = terminals.pull_logs(terminal, test_db)
    terminals.record_pull_outcome(terminal, result)

    assert result.warnings == []
    assert terminal.last_pull_status == "ok" and terminal.last_pull_error is None


def test_stale_warning_needs_a_pointer_driver(test_db):
    """Equipos sin puntero (ZKTeco) entregan siempre toda la memoria: no aplica."""
    terminal = DeviceTerminal(name="Reloj", driver_name="ZKTeco", ip="127.0.0.1", port=4370)
    test_db.add(terminal)
    test_db.commit()

    assert terminals._stale_records_warning(terminal, datetime(2026, 11, 20), date(2020, 1, 1)) is None


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


class _SilentClock:
    """Módulo Tibbo que acepta la conexión TCP pero el reloj detrás no contesta."""

    def __init__(self):
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen()
        self.port = self.server.getsockname()[1]
        self.conns = []
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            self.conns.append(conn)  # abierta y muda

    def close(self):
        for conn in self.conns:
            conn.close()
        self.server.close()


def test_tibbo_answers_but_clock_silent_says_check_terminal():
    from services.addons.base_driver import TerminalCheckError

    silent = _SilentClock()
    try:
        with pytest.raises(TerminalCheckError, match="^Chequear terminal: el módulo Tibbo de 127.0.0.1:") as info:
            SundialDriver().connect({"ip": "127.0.0.1", "port": silent.port, "address": "7", "timeout": 1, "retries": 1})
    finally:
        silent.close()
    assert "terminal 007" in str(info.value)


def test_unreachable_tibbo_is_a_plain_connection_error():
    from services.addons.base_driver import TerminalCheckError

    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()  # puerto sin nadie escuchando

    with pytest.raises(ConnectionError) as info:
        SundialDriver().connect({"ip": "127.0.0.1", "port": port, "timeout": 1, "retries": 1})
    assert not isinstance(info.value, TerminalCheckError)


def test_api_shows_driver_diagnosis_and_hides_other_failures(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import api.routers.terminals as terminal_router
    from api.deps import get_db
    from api.main_api import app
    from core.database import Base
    from core.limiter import limiter
    from core.security import hash_password
    from models.user import AuthUser
    from services.addons.base_driver import TerminalCheckError

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    db = session_factory()
    terminal = DeviceTerminal(name="Sundial", driver_name="Sundial ERTeckno", ip="192.0.2.110", port=3000,
                              connection_params={"ip": "192.0.2.110", "port": "3000", "address": "1"})
    db.add_all([terminal, AuthUser(username="supervisor_sd", password_hash=hash_password("SupervisorPassword!2026"),
                                   role="supervisor", is_active=True, token_version=0)])
    db.commit()

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    failures = iter([
        TerminalCheckError("Chequear terminal: el módulo Tibbo de 192.0.2.110:3000 responde, pero el reloj (terminal 001) no contesta."),
        ConnectionError("Error al conectar con Sundial en 192.0.2.110:3000 - timed out"),
    ])

    def failing_test(_terminal):
        raise next(failures)

    monkeypatch.setattr(terminal_router, "service_test_connection", failing_test)
    app.dependency_overrides[get_db] = override_db
    # El límite de logins es global al proceso: no consumir el cupo de otros tests.
    limiter.reset()
    try:
        with TestClient(app) as client:
            assert client.post("/api/auth/token", data={"username": "supervisor_sd", "password": "SupervisorPassword!2026"}).status_code == 200
            diagnosed = client.post(f"/api/terminals/{terminal.id}/test")
            generic = client.post(f"/api/terminals/{terminal.id}/test")
    finally:
        app.dependency_overrides.clear()
        limiter.reset()

    assert diagnosed.status_code == 400
    assert diagnosed.json()["detail"].startswith("Chequear terminal:")
    assert generic.status_code == 400
    assert generic.json()["detail"] == "No hay conectividad con la terminal"
