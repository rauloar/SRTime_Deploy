from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.deps import get_db
from api.main_api import app
from core.database import Base
from core.security import hash_password
from models import attendance, employee, holiday, processed_attendance, shift, terminal, user  # noqa: F401
from models.employee import TERMINAL_PRIVILEGE_ADMIN, TERMINAL_PRIVILEGE_USER, User
from models.user import AuthUser


def test_employee_csv_import_supports_terminal_privilege_and_legacy_default():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    db = session_factory()
    db.add(AuthUser(
        username="supervisor_import",
        password_hash=hash_password("SupervisorPassword!2026"),
        role="supervisor",
        is_active=True,
        token_version=0,
    ))
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
            login = client.post(
                "/api/auth/token",
                data={"username": "supervisor_import", "password": "SupervisorPassword!2026"},
            )
            assert login.status_code == 200

            csv_with_privilege = (
                "Identificador,Nombre,Apellido,Turno,Privilegio Terminal,Activo\n"
                "42,Ana,Perez,Sin turno,ADMIN,Si\n"
            )
            response = client.post(
                "/api/users/import-csv",
                files={"file": ("empleados.csv", csv_with_privilege, "text/csv")},
            )
            assert response.status_code == 200
            assert response.json()["created"] == 1

            legacy_csv = "Identificador,Nombre,Apellido,Turno,Activo\n43,Juan,Gomez,Sin turno,Si\n"
            response = client.post(
                "/api/users/import-csv",
                files={"file": ("empleados_legacy.csv", legacy_csv, "text/csv")},
            )
            assert response.status_code == 200
            assert response.json()["created"] == 1

        rows = {row.identifier: row for row in db.query(User).all()}
        assert rows["000000000000042"].terminal_privilege == TERMINAL_PRIVILEGE_ADMIN
        assert rows["000000000000043"].terminal_privilege == TERMINAL_PRIVILEGE_USER
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
