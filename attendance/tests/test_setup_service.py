"""First-run setup contract shared by the Web wizard and the desktop dialog."""
import pytest

from core.security import verify_password
from models.user import AuthUser
from services import setup_service
from services.setup_service import SetupError


@pytest.fixture
def sqlite_profile(monkeypatch):
    monkeypatch.setenv("DB_ENGINE", "sqlite")


@pytest.fixture
def blank_postgres_profile(monkeypatch):
    monkeypatch.setenv("DB_ENGINE", "postgres")
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_NAME", "srtime_db")
    monkeypatch.setenv("DB_USER", "")
    monkeypatch.setenv("DB_PASS", "")


def test_sqlite_without_admin_requires_setup(sqlite_profile, test_db):
    assert setup_service.setup_status(test_db) == {
        "setup_required": True, "configured": True, "database_engine": "sqlite",
    }


def test_blank_postgres_profile_requires_database_step(blank_postgres_profile, test_db):
    assert not setup_service.is_database_configured()
    status = setup_service.setup_status(test_db)
    assert status["setup_required"] and not status["configured"]
    assert status["database_engine"] == "postgres"


def test_placeholder_postgres_password_is_not_configured(blank_postgres_profile, monkeypatch):
    monkeypatch.setenv("DB_USER", "postgres")
    monkeypatch.setenv("DB_PASS", "__CHANGE_ME__")
    assert not setup_service.is_database_configured()


def test_create_initial_admin_creates_root_without_forced_change(sqlite_profile, test_db):
    admin = setup_service.create_initial_admin(test_db, "Clave1234", "Clave1234")

    assert admin.username == "admin"
    assert admin.role == "root"
    assert admin.is_active and not admin.must_change_password
    assert verify_password("Clave1234", admin.password_hash)
    assert setup_service.setup_status(test_db)["setup_required"] is False


def test_create_initial_admin_rejects_mismatch(sqlite_profile, test_db):
    with pytest.raises(SetupError) as exc:
        setup_service.create_initial_admin(test_db, "Clave1234", "Clave12345")
    assert not exc.value.conflict
    assert test_db.query(AuthUser).count() == 0


def test_create_initial_admin_applies_password_policy(sqlite_profile, test_db):
    with pytest.raises(SetupError, match="letra y un número"):
        setup_service.create_initial_admin(test_db, "soloLetras", "soloLetras")


def test_create_initial_admin_refuses_second_admin(sqlite_profile, test_db):
    setup_service.create_initial_admin(test_db, "Clave1234", "Clave1234")
    with pytest.raises(SetupError) as exc:
        setup_service.create_initial_admin(test_db, "Otra1234", "Otra1234")
    assert exc.value.conflict
    assert test_db.query(AuthUser).count() == 1


def test_create_initial_admin_requires_database_first(blank_postgres_profile, test_db):
    with pytest.raises(SetupError) as exc:
        setup_service.create_initial_admin(test_db, "Clave1234", "Clave1234")
    assert exc.value.conflict


def test_configure_postgres_rejects_line_breaks(blank_postgres_profile):
    with pytest.raises(SetupError, match="saltos de línea"):
        setup_service.configure_postgres("127.0.0.1", 5432, "postgres", "x\nDB_ENGINE=sqlite", "srtime_db")
