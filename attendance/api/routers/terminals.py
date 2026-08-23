from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, time
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
    pull_logs as service_pull_logs,
)
from services.terminal_scheduler import schedule_next_pull

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


class TerminalScheduleUpdate(BaseModel):
    enabled: bool = False
    interval_minutes: Optional[int] = None
    window_start: Optional[time] = None
    window_end: Optional[time] = None


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
                "pull_schedule": {
                    "enabled": t.pull_schedule_enabled,
                    "interval_minutes": t.pull_interval_minutes,
                    "window_start": t.pull_window_start.isoformat() if t.pull_window_start else None,
                    "window_end": t.pull_window_end.isoformat() if t.pull_window_end else None,
                    "next_pull_at": str(t.next_pull_at) if t.next_pull_at else None,
                    "last_status": t.last_pull_status,
                    "last_error": t.last_pull_error,
                },
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


@router.post("/{terminal_id}/pull")
def pull_terminal_logs_now(
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    """Descarga raw on-demand por el mismo pipeline que el importer."""
    terminal = get_terminal_or_404(terminal_id, db)
    if not terminal.is_active:
        raise HTTPException(status_code=400, detail="La terminal está inactiva")
    try:
        nuevos, duplicados, total, logs_msgs = service_pull_logs(terminal, db)
        terminal.last_pull_status = "ok"
        terminal.last_pull_error = None
        db.commit()
        logger.info("Terminal raw pull completed", extra={"user": current_user.username, "action": "terminal_pull_manual"})
        return {"ok": True, "terminal_name": terminal.name, "total": total, "nuevos": nuevos, "duplicados": duplicados, "logs": logs_msgs[-200:]}
    except (TerminalOperationError, OSError, RuntimeError, ValueError) as exc:
        db.rollback()
        terminal = get_terminal_or_404(terminal_id, db)
        terminal.last_pull_status = "error"
        terminal.last_pull_error = str(exc)[:500]
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{terminal_id}/pull-schedule")
def update_pull_schedule(
    terminal_id: int,
    payload: TerminalScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    terminal = get_terminal_or_404(terminal_id, db)
    if payload.enabled and (payload.interval_minutes is None or payload.interval_minutes < 1):
        raise HTTPException(status_code=422, detail="El intervalo debe ser de al menos un minuto")
    if (payload.window_start is None) != (payload.window_end is None):
        raise HTTPException(status_code=422, detail="Indique inicio y fin de franja, o deje ambos vacíos")
    terminal.pull_schedule_enabled = payload.enabled
    terminal.pull_interval_minutes = payload.interval_minutes if payload.enabled else None
    terminal.pull_window_start = payload.window_start if payload.enabled else None
    terminal.pull_window_end = payload.window_end if payload.enabled else None
    if payload.enabled:
        schedule_next_pull(terminal, datetime.now())
    else:
        terminal.next_pull_at = None
        terminal.last_pull_status = None
        terminal.last_pull_error = None
    db.commit()
    logger.info("Terminal pull schedule updated", extra={"user": current_user.username, "action": "terminal_pull_schedule"})
    return ok_response({"enabled": terminal.pull_schedule_enabled, "next_pull_at": str(terminal.next_pull_at) if terminal.next_pull_at else None})
