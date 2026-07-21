"""
Tests de la capa API FastAPI para el módulo de Asistencia Procesada.
Cubre: feriados (FERIADO en GET), flujo de justificaciones con roles
(request-justify, approve-justify, reject-justify) y control de acceso.
"""
import pytest
from datetime import date, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from api.main_api import app
from api.deps import get_db
from core.security import create_access_token, hash_password as get_password_hash
from models.user import AuthUser
from models.employee import User as Employee
from models.shift import Shift
from models.processed_attendance import ProcessedAttendance
from models.holiday import Holiday

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(scope="module")
def client(api_db):
    def override_get_db():
        yield api_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def seed_data(api_db):
    """Crea usuarios, turno y empleado de prueba una sola vez."""
    shift = Shift(
        id=1, name="Turno Mañana",
        expected_in=time(8, 0), expected_out=time(17, 0),
        grace_period_minutes=15, is_overnight_shift=False,
        break_duration_minutes=60,
    )
    api_db.add(shift)

    emp = Employee(id=1, identifier="EMP001", first_name="Juan", last_name="Perez",
                   shift_id=1, is_active=True)
    api_db.add(emp)

    root_user = AuthUser(
        id=1, username="root_test",
        password_hash=get_password_hash("root1234"),
        role="root", is_active=True, must_change_password=False,
    )
    supervisor_user = AuthUser(
        id=2, username="supervisor_test",
        password_hash=get_password_hash("sup1234"),
        role="supervisor", is_active=True, must_change_password=False,
    )
    viewer_user = AuthUser(
        id=3, username="viewer_test",
        password_hash=get_password_hash("view1234"),
        role="viewer", is_active=True, must_change_password=False,
    )
    api_db.add_all([root_user, supervisor_user, viewer_user])
    api_db.commit()
    return {"shift": shift, "emp": emp}


def token(username: str) -> str:
    return create_access_token({"sub": username})


def auth(username: str) -> dict:
    return {"Authorization": f"Bearer {token(username)}"}


def make_record(api_db, status: str, day: date = None) -> ProcessedAttendance:
    d = day or date.today()
    rec = ProcessedAttendance(
        employee_id=1, date=d, status=status,
        first_in=time(8, 0),
        last_out=time(17, 0) if status != "INCOMPLETO" else None,
        total_hours=8.0 if status != "INCOMPLETO" else 0.0,
        tardiness_minutes=0, early_departure_minutes=0, overtime_minutes=0,
    )
    api_db.add(rec)
    api_db.commit()
    api_db.refresh(rec)
    return rec


# ─────────────────────────────────────────────────────────────────────────────
# Feriados — endpoint GET /api/processed/
# ─────────────────────────────────────────────────────────────────────────────

class TestFeriadoInAPI:

    def test_feriado_record_visible_in_list(self, client, api_db, seed_data):
        """Un registro con status FERIADO aparece en GET /api/processed/."""
        target = date.today() - timedelta(days=10)
        rec = make_record(api_db, "FERIADO", target)

        resp = client.get(
            "/api/processed/",
            params={"date_start": str(target), "date_end": str(target)},
            headers=auth("root_test"),
        )
        assert resp.status_code == 200
        statuses = [r["status"] for r in resp.json()]
        assert "FERIADO" in statuses

        api_db.delete(rec)
        api_db.commit()

    def test_feriado_record_has_zero_tardiness(self, client, api_db, seed_data):
        """Un registro FERIADO devuelto por la API tiene tardiness_minutes == 0."""
        target = date.today() - timedelta(days=11)
        rec = ProcessedAttendance(
            employee_id=1, date=target, status="FERIADO",
            first_in=time(10, 0), last_out=time(14, 0),
            total_hours=4.0, tardiness_minutes=0,
            early_departure_minutes=0, overtime_minutes=0,
        )
        api_db.add(rec)
        api_db.commit()
        api_db.refresh(rec)

        resp = client.get(
            "/api/processed/",
            params={"date_start": str(target), "date_end": str(target)},
            headers=auth("root_test"),
        )
        assert resp.status_code == 200
        records = [r for r in resp.json() if r["status"] == "FERIADO"]
        assert len(records) >= 1
        assert records[0]["tardiness_minutes"] == 0

        api_db.delete(rec)
        api_db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# request-justify
# ─────────────────────────────────────────────────────────────────────────────

class TestRequestJustify:

    def test_supervisor_can_request_justify(self, client, api_db, seed_data):
        """Supervisor puede poner un registro en PENDIENTE."""
        rec = make_record(api_db, "INCOMPLETO", date.today() - timedelta(days=20))

        resp = client.patch(
            f"/api/processed/{rec.id}/request-justify",
            json={"first_in": "08:00", "last_out": "17:00", "justification": "Olvidó fichar salida"},
            headers=auth("supervisor_test"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "PENDIENTE"
        assert body["requested_by"] == "supervisor_test"
        assert body["previous_status"] == "INCOMPLETO"
        assert body["pending_justification"] == "Olvidó fichar salida"

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_root_can_also_request_justify(self, client, api_db, seed_data):
        """Root también puede usar request-justify (tiene permiso supervisor+)."""
        rec = make_record(api_db, "INCOMPLETO", date.today() - timedelta(days=21))

        resp = client.patch(
            f"/api/processed/{rec.id}/request-justify",
            json={"first_in": "08:00", "last_out": "17:00", "justification": "Test root"},
            headers=auth("root_test"),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "PENDIENTE"

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_viewer_cannot_request_justify(self, client, api_db, seed_data):
        """Viewer no puede solicitar justificación (403)."""
        rec = make_record(api_db, "INCOMPLETO", date.today() - timedelta(days=22))

        resp = client.patch(
            f"/api/processed/{rec.id}/request-justify",
            json={"first_in": "08:00", "last_out": "17:00", "justification": "Intento viewer"},
            headers=auth("viewer_test"),
        )
        assert resp.status_code == 403

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_cannot_request_justify_already_pending(self, client, api_db, seed_data):
        """No se puede solicitar justificación si ya hay una pendiente (400)."""
        rec = make_record(api_db, "INCOMPLETO", date.today() - timedelta(days=23))
        # Poner en PENDIENTE manualmente
        rec.status = "PENDIENTE"
        rec.previous_status = "INCOMPLETO"
        rec.requested_by = "supervisor_test"
        api_db.commit()

        resp = client.patch(
            f"/api/processed/{rec.id}/request-justify",
            json={"first_in": "08:00", "last_out": "17:00", "justification": "Duplicado"},
            headers=auth("supervisor_test"),
        )
        assert resp.status_code == 400

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_request_justify_empty_reason_rejected(self, client, api_db, seed_data):
        """Motivo vacío devuelve 400."""
        rec = make_record(api_db, "INCOMPLETO", date.today() - timedelta(days=24))

        resp = client.patch(
            f"/api/processed/{rec.id}/request-justify",
            json={"first_in": "08:00", "last_out": "17:00", "justification": "   "},
            headers=auth("supervisor_test"),
        )
        assert resp.status_code == 400

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# approve-justify
# ─────────────────────────────────────────────────────────────────────────────

class TestApproveJustify:

    def _make_pending(self, api_db, day_offset: int) -> ProcessedAttendance:
        target = date.today() - timedelta(days=day_offset)
        rec = ProcessedAttendance(
            employee_id=1, date=target, status="PENDIENTE",
            previous_status="INCOMPLETO",
            first_in=time(8, 0), last_out=None,
            total_hours=0.0, tardiness_minutes=0,
            early_departure_minutes=0, overtime_minutes=0,
            pending_first_in=time(8, 0), pending_last_out=time(17, 0),
            pending_justification="Motivo válido", requested_by="supervisor_test",
        )
        api_db.add(rec)
        api_db.commit()
        api_db.refresh(rec)
        return rec

    def test_root_can_approve(self, client, api_db, seed_data):
        """Root aprueba solicitud → JUSTIFICADO con horas recalculadas."""
        rec = self._make_pending(api_db, 30)

        resp = client.patch(
            f"/api/processed/{rec.id}/approve-justify",
            headers=auth("root_test"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "JUSTIFICADO"
        assert body["justification"] == "Motivo válido"
        assert body["pending_justification"] is None
        assert body["requested_by"] is None
        assert body["previous_status"] is None
        # 08:00 → 17:00 menos 60 min de descanso = 8.0 horas netas
        assert abs(body["total_hours"] - 8.0) < 0.1

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_supervisor_cannot_approve(self, client, api_db, seed_data):
        """Supervisor no puede aprobar (solo root)."""
        rec = self._make_pending(api_db, 31)

        resp = client.patch(
            f"/api/processed/{rec.id}/approve-justify",
            headers=auth("supervisor_test"),
        )
        assert resp.status_code == 403

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_viewer_cannot_approve(self, client, api_db, seed_data):
        """Viewer no puede aprobar."""
        rec = self._make_pending(api_db, 32)

        resp = client.patch(
            f"/api/processed/{rec.id}/approve-justify",
            headers=auth("viewer_test"),
        )
        assert resp.status_code == 403

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_approve_non_pending_returns_400(self, client, api_db, seed_data):
        """No se puede aprobar un registro que no está PENDIENTE."""
        rec = make_record(api_db, "OK", date.today() - timedelta(days=33))

        resp = client.patch(
            f"/api/processed/{rec.id}/approve-justify",
            headers=auth("root_test"),
        )
        assert resp.status_code == 400

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_approve_missing_record_returns_404(self, client, api_db, seed_data):
        """Aprobar un ID inexistente devuelve 404."""
        resp = client.patch(
            "/api/processed/999999/approve-justify",
            headers=auth("root_test"),
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# reject-justify
# ─────────────────────────────────────────────────────────────────────────────

class TestRejectJustify:

    def _make_pending(self, api_db, day_offset: int,
                      prev_status: str = "INCOMPLETO") -> ProcessedAttendance:
        target = date.today() - timedelta(days=day_offset)
        rec = ProcessedAttendance(
            employee_id=1, date=target, status="PENDIENTE",
            previous_status=prev_status,
            first_in=time(8, 0),
            last_out=time(17, 0) if prev_status != "INCOMPLETO" else None,
            total_hours=8.0 if prev_status != "INCOMPLETO" else 0.0,
            tardiness_minutes=0, early_departure_minutes=0, overtime_minutes=0,
            pending_first_in=time(7, 0), pending_last_out=time(16, 0),
            pending_justification="Solicitud a rechazar", requested_by="supervisor_test",
        )
        api_db.add(rec)
        api_db.commit()
        api_db.refresh(rec)
        return rec

    def test_root_can_reject(self, client, api_db, seed_data):
        """Root rechaza → vuelve a INCOMPLETO, pending limpiado."""
        rec = self._make_pending(api_db, 40)

        resp = client.patch(
            f"/api/processed/{rec.id}/reject-justify",
            headers=auth("root_test"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "INCOMPLETO"
        assert body["pending_justification"] is None
        assert body["requested_by"] is None
        assert body["previous_status"] is None

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_reject_from_ok_restores_ok(self, client, api_db, seed_data):
        """Rechazar desde OK restaura OK."""
        rec = self._make_pending(api_db, 41, prev_status="OK")

        resp = client.patch(
            f"/api/processed/{rec.id}/reject-justify",
            headers=auth("root_test"),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "OK"

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_supervisor_cannot_reject(self, client, api_db, seed_data):
        """Supervisor no puede rechazar (solo root)."""
        rec = self._make_pending(api_db, 42)

        resp = client.patch(
            f"/api/processed/{rec.id}/reject-justify",
            headers=auth("supervisor_test"),
        )
        assert resp.status_code == 403

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_reject_non_pending_returns_400(self, client, api_db, seed_data):
        """Rechazar un registro no PENDIENTE devuelve 400."""
        rec = make_record(api_db, "INCOMPLETO", date.today() - timedelta(days=43))

        resp = client.patch(
            f"/api/processed/{rec.id}/reject-justify",
            headers=auth("root_test"),
        )
        assert resp.status_code == 400

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# justify directo (root only)
# ─────────────────────────────────────────────────────────────────────────────

class TestDirectJustify:

    def test_root_can_justify_directly(self, client, api_db, seed_data):
        """Root justifica directamente sin flujo de aprobación."""
        rec = make_record(api_db, "INCOMPLETO", date.today() - timedelta(days=50))

        resp = client.patch(
            f"/api/processed/{rec.id}/justify",
            json={"first_in": "08:00", "last_out": "17:00", "justification": "Directo root"},
            headers=auth("root_test"),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "JUSTIFICADO"

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_supervisor_cannot_justify_directly(self, client, api_db, seed_data):
        """Supervisor no puede usar el endpoint de justify directo (403)."""
        rec = make_record(api_db, "INCOMPLETO", date.today() - timedelta(days=51))

        resp = client.patch(
            f"/api/processed/{rec.id}/justify",
            json={"first_in": "08:00", "last_out": "17:00", "justification": "Intento supervisor"},
            headers=auth("supervisor_test"),
        )
        assert resp.status_code == 403

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_viewer_cannot_justify_directly(self, client, api_db, seed_data):
        """Viewer no puede justificar directamente (403)."""
        rec = make_record(api_db, "INCOMPLETO", date.today() - timedelta(days=52))

        resp = client.patch(
            f"/api/processed/{rec.id}/justify",
            json={"first_in": "08:00", "last_out": "17:00", "justification": "Intento viewer"},
            headers=auth("viewer_test"),
        )
        assert resp.status_code == 403

        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Autenticación requerida en todos los endpoints nuevos
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthRequired:

    def test_request_justify_requires_auth(self, client, api_db, seed_data):
        rec = make_record(api_db, "INCOMPLETO", date.today() - timedelta(days=60))
        resp = client.patch(
            f"/api/processed/{rec.id}/request-justify",
            json={"first_in": "08:00", "last_out": "17:00", "justification": "x"},
        )
        assert resp.status_code == 401
        api_db.delete(api_db.query(ProcessedAttendance).get(rec.id))
        api_db.commit()

    def test_approve_justify_requires_auth(self, client):
        resp = client.patch("/api/processed/1/approve-justify")
        assert resp.status_code == 401

    def test_reject_justify_requires_auth(self, client):
        resp = client.patch("/api/processed/1/reject-justify")
        assert resp.status_code == 401
