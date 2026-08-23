"""Regression tests for the safe operational Control Center service."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services import operations


def test_backup_status_does_not_expose_full_path(monkeypatch, tmp_path):
    backup = tmp_path / "srtime_20260823_010203.dump"
    backup.write_bytes(b"backup")
    monkeypatch.setenv("SRTIME_BACKUP_DIR", str(tmp_path))

    latest = operations._latest_backup()

    assert latest is not None
    assert latest["name"] == backup.name
    assert str(tmp_path) not in str(latest)


def test_postgres_backup_requires_configured_utility(monkeypatch):
    monkeypatch.setenv("DB_ENGINE", "postgres")
    monkeypatch.delenv("SRTIME_PG_DUMP_PATH", raising=False)
    monkeypatch.setattr(operations.shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="pg_dump"):
        operations.create_postgres_backup()


def test_control_endpoint_is_root_only(monkeypatch):
    from api.deps import get_db
    from api.main_api import app
    from core.database import Base
    from core.security import hash_password
    from models.user import AuthUser

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    db = session_factory()
    db.add_all([
        AuthUser(username="root_operations", password_hash=hash_password("Password2026"), role="root", is_active=True),
        AuthUser(username="viewer_operations", password_hash=hash_password("Password2026"), role="viewer", is_active=True),
    ])
    db.commit()

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr("api.routers.control.get_status", lambda: {"application": {"status": "running"}})
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            assert client.post("/api/auth/token", data={"username": "viewer_operations", "password": "Password2026"}).status_code == 200
            assert client.get("/api/control/status").status_code == 403
            assert client.post("/api/auth/token", data={"username": "root_operations", "password": "Password2026"}).status_code == 200
            assert client.get("/api/control/status").status_code == 200
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
