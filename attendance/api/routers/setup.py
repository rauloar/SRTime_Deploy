"""Local-only first-run configuration, inspired by the WordPress installer."""
import os
from ipaddress import ip_address, ip_network
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import AdminSetupRequest, DatabaseConnectionRequest, DatabaseSetupRequest, SetupStatusResponse
from core.database import SessionLocal, configure_database, engine
from core.init_db import init_database
from core.security import hash_password, validate_password
from models.user import AuthUser

router = APIRouter()
_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def _is_authorized_setup_host(host: str) -> bool:
    """Allow loopback, explicit clients, CIDR ranges, or trusted private LANs."""
    if host in _LOCAL_HOSTS:
        return True
    try:
        client_ip = ip_address(host)
    except ValueError:
        return False
    configured_hosts = [
        value.strip()
        for value in os.getenv("SRTIME_SETUP_ALLOWED_IPS", "").split(",")
        if value.strip()
    ]
    for value in configured_hosts:
        if value.lower() == "private" and client_ip.is_private:
            return True
        try:
            if "/" in value and client_ip in ip_network(value, strict=False):
                return True
        except ValueError:
            continue
        if host == value:
            return True
    return False


def _require_local_request(request: Request) -> None:
    host = request.client.host if request.client else ""
    if not _is_authorized_setup_host(host):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Initial setup is available only from an authorized machine or configured LAN range",
        )


def _configured() -> bool:
    if os.getenv("DB_ENGINE", "sqlite").lower() == "sqlite":
        # SQLite is self-contained: the application owns the database file and
        # needs no external credentials before the first administrator is made.
        return True
    return bool(
        os.getenv("DB_ENGINE") == "postgres"
        and os.getenv("DB_HOST")
        and os.getenv("DB_USER")
        and os.getenv("DB_NAME")
        and os.getenv("DB_PASS")
        and not os.getenv("DB_PASS", "").startswith("__")
    )


def _write_local_config(values: dict[str, str]) -> None:
    env_path = Path(os.environ.get("SRTIME_ENV_FILE", Path(__file__).parents[2] / ".env.pseudo_pro"))
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


def _maintenance_url(body: DatabaseConnectionRequest) -> URL:
    return URL.create(
        "postgresql", username=body.db_user.strip(), password=body.db_password,
        host=body.db_host.strip(), port=body.db_port, database="postgres",
    )


def _quote_identifier(identifier: str) -> str:
    """Identifiers are schema-validated, but quote them as PostgreSQL identifiers too."""
    return '"' + identifier.replace('"', '""') + '"'


@router.get("/status", response_model=SetupStatusResponse)
def setup_status(request: Request, db: Session = Depends(get_db)):
    _require_local_request(request)
    database_engine = os.getenv("DB_ENGINE", "sqlite").lower()
    if not _configured():
        return {"setup_required": True, "configured": False, "database_engine": database_engine}
    try:
        return {
            "setup_required": db.query(AuthUser).count() == 0,
            "configured": True,
            "database_engine": database_engine,
        }
    except SQLAlchemyError:
        # A new SQLite file has no tables yet. Its schema is created by the
        # admin step below, after the operator chooses the initial password.
        return {
            "setup_required": True,
            "configured": database_engine == "sqlite",
            "database_engine": database_engine,
        }


@router.post("/databases")
def list_databases(body: DatabaseConnectionRequest, request: Request):
    """List selectable databases after verifying the supplied PostgreSQL connection."""
    _require_local_request(request)
    try:
        engine = create_engine(_maintenance_url(body))
        with engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT datname FROM pg_database "
                "WHERE datistemplate = FALSE ORDER BY datname"
            )).scalars().all()
        engine.dispose()
        return {"databases": rows}
    except (SQLAlchemyError, UnicodeDecodeError, OSError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Could not list PostgreSQL databases. Verify host, port, user, and password.",
        ) from exc
@router.post("/database", status_code=status.HTTP_201_CREATED)
def create_database(body: DatabaseSetupRequest, request: Request):
    """Create/connect the SRTime database, then enable creation of the app admin."""
    _require_local_request(request)
    if any("\n" in value or "\r" in value for value in (body.db_host, body.db_user, body.db_password, body.db_name)):
        raise HTTPException(status_code=400, detail="Database settings cannot contain line breaks")

    settings = {
        "DB_ENGINE": "postgres",
        "DB_HOST": body.db_host.strip(),
        "DB_PORT": str(body.db_port),
        "DB_USER": body.db_user.strip(),
        "DB_PASS": body.db_password,
        "DB_NAME": body.db_name,
        "SRTIME_DEFER_ADMIN_SETUP": "true",
    }
    maintenance_engine = None
    try:
        maintenance_engine = create_engine(_maintenance_url(body), isolation_level="AUTOCOMMIT")
        with maintenance_engine.connect() as connection:
            exists = connection.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": body.db_name}).scalar()
            if not exists:
                connection.execute(text(f"CREATE DATABASE {_quote_identifier(body.db_name)}"))
        _write_local_config(settings)
        os.environ.update(settings)
        target_engine = configure_database(settings)
        # The first SRTime user is deliberately created only by /admin.
        init_database(target_engine, defer_admin_setup=True)
    except (SQLAlchemyError, UnicodeDecodeError, OSError) as exc:
        # psycopg2 may raise UnicodeDecodeError while decoding a localized
        # PostgreSQL authentication error (for example, a Spanish server).
        raise HTTPException(
            status_code=400,
            detail="PostgreSQL rejected the connection. Verify host, port, user, password, and CREATE DATABASE permission.",
        ) from exc
    finally:
        if maintenance_engine is not None:
            maintenance_engine.dispose()

    return {"ok": True, "message": "Database configured. You can now create the SRTime administrator."}


@router.post("/admin", status_code=status.HTTP_201_CREATED)
def create_initial_admin(body: AdminSetupRequest, request: Request):
    """Create the first SRTime account after the database connection is ready."""
    _require_local_request(request)
    if not _configured():
        raise HTTPException(status_code=409, detail="Create the PostgreSQL database connection first")
    if body.admin_password != body.confirm_admin_password:
        raise HTTPException(status_code=400, detail="Administrator passwords do not match")
    try:
        validate_password(body.admin_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        if os.getenv("DB_ENGINE", "sqlite").lower() == "sqlite":
            # For the desktop profile, create the local schema only when the
            # operator completes this wizard. No default login is seeded.
            init_database(engine, defer_admin_setup=True)
        with SessionLocal() as db:
            if db.query(AuthUser).count() > 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SRTime already has an administrator")
            db.add(AuthUser(
                username="admin", password_hash=hash_password(body.admin_password),
                role="root", is_active=True, must_change_password=False,
            ))
            db.commit()
    except HTTPException:
        raise
    except (SQLAlchemyError, UnicodeDecodeError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Could not create the SRTime administrator") from exc

    return {"ok": True, "message": "SRTime administrator created"}
