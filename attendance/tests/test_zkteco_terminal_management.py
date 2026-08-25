from datetime import datetime
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.routers.terminals as terminal_router
from api.deps import get_db
from api.main_api import app
from core.database import Base
from core.security import hash_password
from models.employee import User
from models.terminal import DeviceTerminal
from models.user import AuthUser
from services import terminals
from services.addons.zkteco.driver import ZKTecoDriver
from services.addons.zkteco.__manifest__ import manifest


class _Attendance:
    user_id = "42"
    timestamp = datetime(2026, 8, 24, 6, 15)
    status = 0


class _DeviceUser:
    uid = 17
    user_id = "42"
    name = "Nombre anterior"
    privilege = 14
    password = "keep"
    group_id = "group-a"
    card = 99


class _Connection:
    user_packet_size = 72

    def __init__(self):
        self.attendance_calls = 0
        self.set_calls = []

    def get_attendance(self):
        self.attendance_calls += 1
        return [_Attendance()]

    def get_users(self):
        return [_DeviceUser()]

    def set_user(self, **kwargs):
        self.set_calls.append(kwargs)


def test_zkteco_management_preserves_terminal_identity_and_privileges():
    connection = _Connection()
    driver = ZKTecoDriver()
    driver.conn = connection

    assert driver.get_attendance_log_count() == 1
    assert list(driver.get_attendance_logs())[0][0] == "000000000000042"
    assert connection.attendance_calls == 1

    device_user = driver.get_terminal_users()[0]
    driver.update_terminal_user_name(device_user, "Pérez Ana")

    assert connection.set_calls == [{
        "uid": 17,
        "user_id": "42",
        "name": "Pérez Ana",
        "privilege": 14,
        "password": "keep",
        "group_id": "group-a",
        "card": 99,
    }]
    assert driver.get_terminal_user_name_max_bytes() == 24


def test_zkteco_manifest_declares_only_the_validated_connection_fields():
    fields = {field["name"]: field for field in manifest["connection_fields"]}

    assert set(fields) == {"ip", "port"}
    assert fields["port"]["default"] == "4370"
    assert manifest["capabilities"]["terminal_users"] is True


def test_zkteco_connect_uses_the_validated_pyzk_call(monkeypatch):
    captured = {}

    class _ZK:
        def __init__(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

        def connect(self):
            return SimpleNamespace(disable_device=lambda: None)

    monkeypatch.setitem(sys.modules, "zk", SimpleNamespace(ZK=_ZK))
    driver = ZKTecoDriver()

    driver.connect({"ip": "192.0.2.201", "port": "4370"})

    assert captured == {
        "args": ("192.0.2.201",),
        "kwargs": {"port": 4370},
    }


def test_name_sync_updates_only_names_for_matching_employees(test_db, monkeypatch):
    class _ManagedDriver:
        def __init__(self):
            self.connected = False
            self.disconnected = False
            self.updated = []

        def connect(self, _params):
            self.connected = True

        def disconnect(self):
            self.disconnected = True

        def get_terminal_users(self):
            return [{
                "uid": 17, "user_id": "42", "name": "Nombre anterior",
                "privilege": 14, "password": "keep", "group_id": "group-a", "card": 99,
            }]

        def get_terminal_user_name_max_bytes(self):
            return 24

        def update_terminal_user_name(self, user, name):
            self.updated.append((user, name))

    driver = _ManagedDriver()
    terminal = DeviceTerminal(name="Terminal de prueba", driver_name="Any managed driver", ip="127.0.0.1", port=1)
    test_db.add_all([terminal, User(identifier="000000000000042", first_name="Ana", last_name="Perez")])
    test_db.commit()
    monkeypatch.setattr(terminals, "get_addon_info", lambda _terminal: {
        "manifest": {"capabilities": {"terminal_user_name_sync": True}}
    })
    monkeypatch.setattr(terminals, "get_driver_instance", lambda _terminal: driver)

    result = terminals.sync_terminal_user_names(terminal, test_db)

    assert result["updated"] == 1
    assert driver.updated[0][1] == "Perez Ana"
    assert driver.updated[0][0]["uid"] == 17
    assert driver.updated[0][0]["user_id"] == "42"
    assert driver.updated[0][0]["privilege"] == 14
    assert driver.disconnected is True


def test_terminal_management_api_exposes_only_safe_device_user_data(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    db = session_factory()
    terminal = DeviceTerminal(
        name="Reloj ZK",
        driver_name="ZKTeco",
        ip="192.0.2.201",
        port=4370,
        connection_params={"ip": "192.0.2.201", "port": "4370"},
    )
    db.add_all([
        terminal,
        AuthUser(
            username="supervisor_zk",
            password_hash=hash_password("SupervisorPassword!2026"),
            role="supervisor",
            is_active=True,
            token_version=0,
        ),
    ])
    db.commit()

    def override_db():
        test_session = session_factory()
        try:
            yield test_session
        finally:
            test_session.close()

    monkeypatch.setattr(terminal_router, "service_list_terminal_users", lambda _terminal: {
        "users": [{
            "uid": 7,
            "user_id": "42",
            "name": "Ana",
            "privilege": 14,
            "privilege_label": "Administrador de terminal",
        }],
        "name_max_bytes": 24,
    })
    monkeypatch.setattr(terminal_router, "service_sync_terminal_user_names", lambda _terminal, _db: {
        "terminal_users": 1, "updated": 1, "matched": 1, "name_max_bytes": 24,
    })
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            login = client.post("/api/auth/token", data={"username": "supervisor_zk", "password": "SupervisorPassword!2026"})
            assert login.status_code == 200

            users = client.get(f"/api/terminals/{terminal.id}/device-users")
            assert users.status_code == 200
            assert users.json()["users"] == [{
                "uid": 7,
                "user_id": "42",
                "name": "Ana",
                "privilege": 14,
                "privilege_label": "Administrador de terminal",
            }]
            assert "password" not in str(users.json()).lower()

            sync = client.post(f"/api/terminals/{terminal.id}/sync-user-names")
            assert sync.status_code == 200
            assert sync.json()["updated"] == 1
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
