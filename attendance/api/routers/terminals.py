from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Optional

from api.deps import get_db, get_current_user, get_terminal_or_404, ok_response, require_root, require_supervisor_or_root
from models.user import AuthUser
from models.terminal import DeviceTerminal
from core.logging_config import get_logger
from services.constants import DEFAULT_ZKTECO_PORT
from services.terminals import (
    SECRET_FIELDS,
    TerminalOperationError,
    merge_connection_params,
    public_connection_params,
    sync_time as service_sync_time,
    test_connection as service_test_connection,
)

logger = get_logger(__name__)

router = APIRouter()


class TerminalCreate(BaseModel):
    name: str
    driver_name: str
    ip: Optional[str] = None
    port: Optional[int] = DEFAULT_ZKTECO_PORT
    password: Optional[str] = None
    connection_params: Optional[dict[str, Any]] = None
    is_active: bool = True

class TerminalUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None
    connection_params: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


@router.get("/")
def list_terminals(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    terminals = db.query(DeviceTerminal).order_by(DeviceTerminal.id).all()
    return {
        "terminals": [
            {
                "id": t.id,
                "name": t.name,
                "driver_name": t.driver_name,
                "ip": t.ip,
                "port": t.port,
                "connection_params": public_connection_params(t),
                "has_password": bool(
                    any((t.connection_params or {}).get(key) for key in SECRET_FIELDS)
                    or t.password
                ),
                "serial_number": t.serial_number,
                "is_active": t.is_active,
                "last_sync": str(t.last_sync) if t.last_sync else None,
                "created_at": str(t.created_at) if t.created_at else None,
            }
            for t in terminals
        ]
    }


@router.post("/")
def create_terminal(
    payload: TerminalCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    terminal = DeviceTerminal(
        name=payload.name,
        driver_name=payload.driver_name,
        ip=payload.ip,
        port=payload.port,
        password=None,
        is_active=payload.is_active,
    )
    terminal.connection_params = merge_connection_params(
        terminal,
        payload.connection_params or {
            "ip": payload.ip,
            "port": str(payload.port) if payload.port is not None else None,
            "password": payload.password,
        },
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)
    logger.info(f"Terminal created: {terminal.name} ({terminal.ip}:{terminal.port})",
                extra={"user": current_user.username, "action": "terminal_create"})
    return ok_response({"id": terminal.id})


@router.put("/{terminal_id}")
def update_terminal(
    terminal_id: int,
    payload: TerminalUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    terminal = get_terminal_or_404(terminal_id, db)
    data = payload.model_dump(exclude={"connection_params"}, exclude_none=True)
    for key, value in data.items():
        setattr(terminal, key, value)
    if payload.connection_params is not None:
        terminal.connection_params = merge_connection_params(terminal, payload.connection_params)
    db.commit()
    logger.info(f"Terminal updated: {terminal.name}",
                extra={"user": current_user.username, "action": "terminal_update"})
    return ok_response()


@router.delete("/{terminal_id}")
def delete_terminal(
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_root),
):
    terminal = get_terminal_or_404(terminal_id, db)
    name = terminal.name
    db.delete(terminal)
    db.commit()
    logger.info(f"Terminal deleted: {name}",
                extra={"user": current_user.username, "action": "terminal_delete"})
    return ok_response()


@router.post("/{terminal_id}/test")
def test_terminal(
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    terminal = get_terminal_or_404(terminal_id, db)

    try:
        result = service_test_connection(terminal)
        sn = result.get("serial_number") or result.get("mac")
        if sn and not terminal.serial_number:
            terminal.serial_number = sn
            db.commit()
        logger.info(f"Terminal test OK: {terminal.name} ({terminal.ip})",
                    extra={"user": current_user.username, "action": "terminal_test"})
        return result
    except (TerminalOperationError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{terminal_id}/sync")
def sync_terminal_time(
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    terminal = get_terminal_or_404(terminal_id, db)

    try:
        ok = service_sync_time(terminal)
        logger.info(f"Terminal sync: {terminal.name}",
                    extra={"user": current_user.username, "action": "terminal_sync"})
        return ok_response({"ok": ok})
    except (TerminalOperationError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
