"""First-run setup shared by the Web wizard and the PySide6 desktop dialog.

Both faces of the suite follow the same sequence: connect or create the
database (PostgreSQL only; SQLite is owned by the application) and then create
the single initial ``admin`` account chosen by the operator. No default login
or password is ever seeded.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import core.database as database
from core.config import resolve_env_path
from core.init_db import init_database
from core.security import hash_password, validate_password
from models.user import AuthUser

INITIAL_ADMIN_USERNAME = "admin"
INITIAL_ADMIN_ROLE = "root"

# Fallbacks for the proposed database step. The local profile (written by the
# installer with the detected PostgreSQL port) always takes precedence.
DEFAULT_CONNECTION = {"db_host": "localhost", "db_port": 5432, "db_user": "postgres", "db_name": "srtime_db"}


class SetupError(Exception):
    """Setup failure with a user-facing message; ``conflict`` maps to HTTP 409."""

    def __init__(self, message: str, *, conflict: bool = False):
        super().__init__(message)
        self.message = message
        self.conflict = conflict


def database_engine() -> str:
    return os.getenv("DB_ENGINE", "sqlite").lower()


def is_database_configured() -> bool:
    if database_engine() == "sqlite":
        # SQLite is self-contained: the application owns the database file and
        # needs no external credentials before the first administrator is made.
        return True
    return bool(
        database_engine() == "postgres"
        and os.getenv("DB_HOST")
        and os.getenv("DB_USER")
        and os.getenv("DB_NAME")
        and os.getenv("DB_PASS")
        and not os.getenv("DB_PASS", "").startswith("__")
    )


def _configured_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    return "" if value.startswith("__") else value


def suggested_connection() -> dict:
    """Values proposed by both wizards; the password is never returned."""
    port = _configured_value("DB_PORT")
    return {
        "db_host": _configured_value("DB_HOST") or DEFAULT_CONNECTION["db_host"],
        "db_port": int(port) if port.isdigit() else DEFAULT_CONNECTION["db_port"],
        "db_user": _configured_value("DB_USER") or DEFAULT_CONNECTION["db_user"],
        "db_name": _configured_value("DB_NAME") or DEFAULT_CONNECTION["db_name"],
    }


def setup_status(session: Session | None) -> dict:
    """Return the same status contract used by ``GET /api/setup/status``."""
    engine_name = database_engine()
    status = {"database_engine": engine_name, "suggested_connection": suggested_connection()}
    if not is_database_configured() or session is None:
        return {"setup_required": True, "configured": False, **status}
    try:
        return {"setup_required": session.query(AuthUser).count() == 0, "configured": True, **status}
    except SQLAlchemyError:
        # A new SQLite file has no tables yet. Its schema is created by the
        # admin step, after the operator chooses the initial password.
        session.rollback()
        return {"setup_required": True, "configured": engine_name == "sqlite", **status}


def _maintenance_url(host: str, port: int, user: str, password: str) -> URL:
    return URL.create(
        "postgresql", username=user.strip(), password=password,
        host=host.strip(), port=port, database="postgres",
    )


def _quote_identifier(identifier: str) -> str:
    """Identifiers are schema-validated, but quote them as PostgreSQL identifiers too."""
    return '"' + identifier.replace('"', '""') + '"'


def _write_local_config(values: dict[str, str]) -> None:
    env_path = resolve_env_path()
    current: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                current[key.strip()] = value.strip()
    current.update(values)
    content = "\n".join(f"{key}={value}" for key, value in current.items()) + "\n"
    temp_path = env_path.with_suffix(env_path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    os.replace(temp_path, env_path)


def list_databases(host: str, port: int, user: str, password: str) -> list[str]:
    """List selectable databases after verifying the supplied PostgreSQL connection."""
    try:
        engine = create_engine(_maintenance_url(host, port, user, password))
        with engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT datname FROM pg_database "
                "WHERE datistemplate = FALSE ORDER BY datname"
            )).scalars().all()
        engine.dispose()
        return list(rows)
    except (SQLAlchemyError, UnicodeDecodeError, OSError) as exc:
        raise SetupError(
            "No se pudieron listar las bases de PostgreSQL. Verificá servidor, puerto, usuario y contraseña."
        ) from exc


def configure_postgres(host: str, port: int, user: str, password: str, db_name: str) -> None:
    """Create/connect the SRTime database and persist it in the local profile."""
    if any("\n" in value or "\r" in value for value in (host, user, password, db_name)):
        raise SetupError("Los datos de la base no pueden contener saltos de línea")

    settings = {
        "DB_ENGINE": "postgres",
        "DB_HOST": host.strip(),
        "DB_PORT": str(port),
        "DB_USER": user.strip(),
        "DB_PASS": password,
        "DB_NAME": db_name,
        "SRTIME_DEFER_ADMIN_SETUP": "true",
    }
    maintenance_engine = None
    try:
        maintenance_engine = create_engine(
            _maintenance_url(host, port, user, password), isolation_level="AUTOCOMMIT"
        )
        with maintenance_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
            ).scalar()
            if not exists:
                connection.execute(text(f"CREATE DATABASE {_quote_identifier(db_name)}"))
        _write_local_config(settings)
        os.environ.update(settings)
        target_engine = database.configure_database(settings)
        # The first SRTime user is deliberately created only by create_initial_admin.
        init_database(target_engine, defer_admin_setup=True)
    except (SQLAlchemyError, UnicodeDecodeError, OSError) as exc:
        # psycopg2 may raise UnicodeDecodeError while decoding a localized
        # PostgreSQL authentication error (for example, a Spanish server).
        raise SetupError(
            "PostgreSQL rechazó la conexión. Verificá servidor, puerto, usuario, contraseña y permiso CREATE DATABASE."
        ) from exc
    finally:
        if maintenance_engine is not None:
            maintenance_engine.dispose()


def create_initial_admin(session: Session, password: str, confirmation: str) -> AuthUser:
    """Create the first SRTime account once the database connection is ready."""
    if not is_database_configured():
        raise SetupError("Primero creá o conectá la base de datos PostgreSQL", conflict=True)
    if password != confirmation:
        raise SetupError("Las contraseñas de administrador no coinciden")
    try:
        validate_password(password)
    except ValueError as exc:
        raise SetupError(str(exc)) from exc

    try:
        if database_engine() == "sqlite":
            # For the desktop profile, create the local schema only when the
            # operator completes this step. No default login is seeded.
            init_database(session.get_bind(), defer_admin_setup=True)
        if session.query(AuthUser).count() > 0:
            raise SetupError("SRTime ya tiene un administrador", conflict=True)
        admin = AuthUser(
            username=INITIAL_ADMIN_USERNAME, password_hash=hash_password(password),
            role=INITIAL_ADMIN_ROLE, is_active=True, must_change_password=False,
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        return admin
    except SetupError:
        raise
    except (SQLAlchemyError, UnicodeDecodeError, OSError) as exc:
        session.rollback()
        raise SetupError("No se pudo crear el administrador de SRTime") from exc
