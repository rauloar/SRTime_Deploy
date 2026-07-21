"""Contratos de seguridad HTTP y RBAC."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.deps import get_db
from api.main_api import app
from core.database import Base
from core.security import hash_password
from models import attendance, employee, holiday, processed_attendance, shift, terminal, user  # noqa: F401
from models.terminal import DeviceTerminal
from models.user import AuthUser


def _login(client: TestClient, username: str, password: str):
    return client.post(
        "/api/auth/token",
        data={"username": username, "password": password},
    )


def test_cookie_auth_rbac_and_terminal_secret_redaction():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    db = session_factory()
    db.add_all([
        AuthUser(
            username="root_security",
            password_hash=hash_password("RootPassword!2026"),
            role="root",
            is_active=True,
            token_version=0,
        ),
        AuthUser(
            username="viewer_security",
            password_hash=hash_password("ViewerPassword!2026"),
            role="viewer",
            is_active=True,
            token_version=0,
        ),
        DeviceTerminal(
            name="Reloj",
            driver_name="Hikvision (ISAPI)",
            ip="10.0.0.5",
            connection_params={"ip": "10.0.0.5", "password": "enc:not-returned"},
        ),
    ])
    db.commit()

    def override_db():
        test_session = session_factory()
        try:
            yield test_session
        finally:
            test_session.close()

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = _login(client, "viewer_security", "ViewerPassword!2026")
            assert response.status_code == 200
            assert "httponly" in response.headers["set-cookie"].lower()

            terminals = client.get("/api/terminals/")
            assert terminals.status_code == 200
            payload = terminals.json()["terminals"][0]
            assert "password" not in payload
            assert payload["connection_params"] == {"ip": "10.0.0.5"}

            forbidden = client.post("/api/terminals/", json={
                "name": "No autorizado",
                "driver_name": "ZKTeco",
                "connection_params": {"ip": "127.0.0.1"},
            })
            assert forbidden.status_code == 403
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
