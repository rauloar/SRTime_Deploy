"""
Contratos de API que usan las pestañas Web de Feriados, Reportes y ui.ini,
alineadas con SRTime_Win (misma fuente de datos, mismas reglas).
"""
from datetime import MAXYEAR, date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.deps import get_db
from api.main_api import app
from core.database import Base
from core.security import create_access_token, hash_password
from core.ui_settings import FIXED_TABS, OPTIONAL_TABS
from models.employee import User as Employee
from models.holiday import NAME_MAX_LENGTH, Holiday
from models.processed_attendance import ProcessedAttendance
from models.shift import Shift
from models.user import AuthUser
from services.reports import MONTHLY_REPORT_COLUMNS


@pytest.fixture(scope="module")
def api_db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    for user_id, username, role in ((1, "root_parity", "root"), (2, "sup_parity", "supervisor"), (3, "viewer_parity", "viewer")):
        session.add(AuthUser(
            id=user_id, username=username, password_hash=hash_password("Parity1234"),
            role=role, is_active=True, must_change_password=False,
        ))
    session.add(Shift(
        id=1, name="Turno", expected_in=time(8, 0), expected_out=time(17, 0),
        grace_period_minutes=10, is_overnight_shift=False, break_duration_minutes=0,
    ))
    session.add(Employee(id=1, identifier="P001", first_name="Ana", last_name="Gomez", shift_id=1, is_active=True))
    session.add(ProcessedAttendance(
        employee_id=1, date=date(2026, 3, 2), status="OK",
        tardiness_minutes=5, overtime_minutes=0, total_hours=8.0,
    ))
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(scope="module")
def client(api_db):
    app.dependency_overrides[get_db] = lambda: api_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth(username: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': username})}"}


# ── Feriados ─────────────────────────────────────────────────────────────────

def test_holiday_crud_with_date_change(client, api_db):
    created = client.post("/api/holidays/", json={"date": "2026-05-01", "name": "  Día del Trabajador  "}, headers=auth("sup_parity"))
    assert created.status_code == 201
    holiday = created.json()
    assert holiday["name"] == "Día del Trabajador"

    moved = client.put(f"/api/holidays/{holiday['id']}", json={"date": "2026-05-02", "is_recurring": True}, headers=auth("sup_parity"))
    assert moved.status_code == 200
    assert moved.json()["date"] == "2026-05-02"
    assert moved.json()["is_recurring"] is True

    assert client.delete(f"/api/holidays/{holiday['id']}", headers=auth("sup_parity")).status_code == 403
    assert client.delete(f"/api/holidays/{holiday['id']}", headers=auth("root_parity")).status_code == 204


def test_holiday_date_change_rejects_duplicates(client, api_db):
    api_db.add_all([Holiday(date=date(2026, 7, 9), name="Independencia"), Holiday(date=date(2026, 7, 10), name="Puente")])
    api_db.commit()
    other = api_db.query(Holiday).filter_by(date=date(2026, 7, 10)).one()
    response = client.put(f"/api/holidays/{other.id}", json={"date": "2026-07-09"}, headers=auth("root_parity"))
    assert response.status_code == 400


@pytest.mark.parametrize("name", ["   ", "x" * (NAME_MAX_LENGTH + 1)])
def test_holiday_name_is_validated(client, name):
    response = client.post("/api/holidays/", json={"date": "2026-08-17", "name": name}, headers=auth("root_parity"))
    assert response.status_code == 422


def test_viewer_cannot_create_holiday(client):
    response = client.post("/api/holidays/", json={"date": "2026-10-12", "name": "Diversidad"}, headers=auth("viewer_parity"))
    assert response.status_code == 403


# ── Reportes ─────────────────────────────────────────────────────────────────

def test_monthly_report_publishes_shared_columns(client):
    response = client.get("/api/reports/monthly", params={"year": 2026, "month": 3}, headers=auth("viewer_parity"))
    assert response.status_code == 200
    body = response.json()
    assert [column["key"] for column in body["columns"]] == [key for key, _ in MONTHLY_REPORT_COLUMNS]
    assert body["employees"][0]["ok"] == 1


def test_monthly_report_rejects_out_of_range_year(client):
    response = client.get("/api/reports/monthly", params={"year": MAXYEAR + 1, "month": 1}, headers=auth("root_parity"))
    assert response.status_code == 422


@pytest.mark.parametrize("path, extension", [("/api/reports/monthly/export", "xlsx"), ("/api/reports/monthly/export/pdf", "pdf")])
def test_monthly_exports_name_the_file(client, path, extension):
    response = client.get(path, params={"year": 2026, "month": 3}, headers=auth("root_parity"))
    assert response.status_code == 200
    assert f"filename=reporte_marzo_2026.{extension}" in response.headers["content-disposition"]


def test_reports_require_authentication(client):
    assert client.get("/api/reports/monthly", params={"year": 2026, "month": 3}).status_code == 401


# ── ui.ini ───────────────────────────────────────────────────────────────────

def test_ui_settings_reads_the_same_ini_as_desktop(client, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    (tmp_path / "ui.ini").write_text("[pestanas]\nferiados = false\nmovimientos = false\n", encoding="utf-8")
    monkeypatch.setenv("SRTIME_ENV_FILE", str(env_file))

    response = client.get("/api/ui/settings", headers=auth("viewer_parity"))
    assert response.status_code == 200
    body = response.json()
    assert body["hidden_tabs"] == ["feriados"]
    assert set(body["fixed_tabs"]) == FIXED_TABS
    assert set(body["optional_tabs"]) == OPTIONAL_TABS


def test_ui_settings_require_authentication(client):
    assert client.get("/api/ui/settings").status_code == 401
