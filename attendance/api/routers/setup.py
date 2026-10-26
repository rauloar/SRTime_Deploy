"""Local-only first-run configuration, inspired by the WordPress installer.

The setup logic lives in ``services.setup_service`` and is shared with the
PySide6 desktop dialog; this router only adds LAN authorization and HTTP.
"""
import os
from ipaddress import ip_address, ip_network

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import AdminSetupRequest, DatabaseConnectionRequest, DatabaseSetupRequest, SetupStatusResponse
from core.database import SessionLocal
from services import setup_service
from services.setup_service import SetupError

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


def _http_error(exc: SetupError) -> HTTPException:
    return HTTPException(status_code=409 if exc.conflict else 400, detail=exc.message)


@router.get("/status", response_model=SetupStatusResponse)
def setup_status(request: Request, db: Session = Depends(get_db)):
    _require_local_request(request)
    return setup_service.setup_status(db)


@router.post("/databases")
def list_databases(body: DatabaseConnectionRequest, request: Request):
    """List selectable databases after verifying the supplied PostgreSQL connection."""
    _require_local_request(request)
    try:
        return {"databases": setup_service.list_databases(body.db_host, body.db_port, body.db_user, body.db_password)}
    except SetupError as exc:
        raise _http_error(exc) from exc


@router.post("/database", status_code=status.HTTP_201_CREATED)
def create_database(body: DatabaseSetupRequest, request: Request):
    """Create/connect the SRTime database, then enable creation of the app admin."""
    _require_local_request(request)
    try:
        setup_service.configure_postgres(body.db_host, body.db_port, body.db_user, body.db_password, body.db_name)
    except SetupError as exc:
        raise _http_error(exc) from exc
    return {"ok": True, "message": "Database configured. You can now create the SRTime administrator."}


@router.post("/admin", status_code=status.HTTP_201_CREATED)
def create_initial_admin(body: AdminSetupRequest, request: Request):
    """Create the first SRTime account after the database connection is ready."""
    _require_local_request(request)
    # A fresh session binds to the engine selected by /database, if any.
    with SessionLocal() as db:
        try:
            setup_service.create_initial_admin(db, body.admin_password, body.confirm_admin_password)
        except SetupError as exc:
            raise _http_error(exc) from exc
    return {"ok": True, "message": "SRTime administrator created"}
