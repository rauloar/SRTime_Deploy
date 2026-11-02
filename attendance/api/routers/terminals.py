from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date, time
from typing import Any, Literal, Optional

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
    set_attendance_pointer as service_set_attendance_pointer,
    sync_time as service_sync_time,
    test_connection as service_test_connection,
    with_enabled_driver,
    pull_warnings,
    run_pull as service_run_pull,
    list_terminal_users as service_list_terminal_users,
    sync_terminal_user_names as service_sync_terminal_user_names,
)
from services.addons.base_driver import TerminalCheckError
from services.terminal_scheduler import ScheduleError, apply_pull_schedule, schedule_state
from core.database import SessionLocal
from core.operation_status import operation_status

logger = get_logger(__name__)

router = APIRouter()


class _TerminalPullProgress:
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id

    def set_total(self, total: int) -> None:
        operation_status.update(self.job_id, current=0, total=total, message="Registros detectados; iniciando descarga")

    def emit(self, current: int, nuevos: int, duplicados: int, message: str) -> None:
        operation_status.update(
            self.job_id,
            current=current,
            message=f"{message} ({nuevos} nuevos, {duplicados} duplicados)",
        )


def _run_terminal_pull_job(job_id: str, terminal_id: int, username: str, clear_device_memory: bool = False) -> None:
    db = SessionLocal()
    try:
        terminal = get_terminal_or_404(terminal_id, db)
        result = service_run_pull(
            terminal,
            db,
            progress_signal=_TerminalPullProgress(job_id),
            clear_device_memory=clear_device_memory,
        )
        nuevos, duplicados, total, logs_msgs = result
        operation_status.complete(
            job_id,
            {"terminal_name": terminal.name, "total": total, "nuevos": nuevos, "duplicados": duplicados,
             "logs": logs_msgs[-200:], "warnings": pull_warnings(result)},
            f"Descarga completada: {nuevos} nuevos, {duplicados} duplicados",
        )
        logger.info("Terminal raw pull job completed", extra={"user": username, "action": "terminal_pull_job"})
    except Exception as exc:
        # run_pull ya dejó el error en la terminal.
        db.rollback()
        operation_status.fail(job_id, f"Error al descargar registros: {exc}")
        logger.exception("Terminal raw pull job failed", extra={"user": username, "action": "terminal_pull_job"})
    finally:
        db.close()


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
    mode: Literal["interval", "weekly"] = "interval"
    interval_minutes: Optional[int] = None
    weekdays: Optional[list[int]] = None
    scheduled_time: Optional[time] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    window_start: Optional[time] = None
    window_end: Optional[time] = None


class TerminalPullRequest(BaseModel):
    clear_device_memory: bool = False


class TerminalPointerRequest(BaseModel):
    since: date


@router.get("/")
def list_terminals(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    terminals = with_enabled_driver(db.query(DeviceTerminal)).order_by(DeviceTerminal.id).all()
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
                "pull_schedule": schedule_state(t),
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
    except Exception as exc:
        logger.exception(
            "Terminal connectivity test failed",
            extra={
                "user": current_user.username,
                "action": "terminal_test_failed",
                "terminal_id": terminal.id,
                "terminal_name": terminal.name,
                "driver_name": terminal.driver_name,
                "ip": terminal.ip,
                "port": terminal.port,
            },
        )
        # Un diagnóstico del driver (TerminalCheckError) llega tal cual al operador;
        # cualquier otro fallo se informa genérico y el detalle queda en el log.
        detail = str(exc) if isinstance(exc, TerminalCheckError) else "No hay conectividad con la terminal"
        raise HTTPException(status_code=400, detail=detail) from exc


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


@router.post("/{terminal_id}/pointer")
def set_terminal_attendance_pointer(
    terminal_id: int,
    payload: TerminalPointerRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    """Reposiciona la lectura del equipo; la próxima descarga trae desde esa fecha."""
    terminal = get_terminal_or_404(terminal_id, db)
    if not terminal.is_active:
        raise HTTPException(status_code=400, detail="La terminal está inactiva")
    try:
        ok = service_set_attendance_pointer(terminal, payload.since)
        logger.info(
            f"Terminal pointer set: {terminal.name} since {payload.since}",
            extra={"user": current_user.username, "action": "terminal_pointer"},
        )
        return ok_response({"ok": ok})
    except (TerminalOperationError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{terminal_id}/pull")
def pull_terminal_logs_now(
    terminal_id: int,
    payload: TerminalPullRequest | None = None,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    """Descarga raw on-demand por el mismo pipeline que el importer."""
    terminal = get_terminal_or_404(terminal_id, db)
    if not terminal.is_active:
        raise HTTPException(status_code=400, detail="La terminal está inactiva")
    try:
        result = service_run_pull(
            terminal,
            db,
            clear_device_memory=bool(payload and payload.clear_device_memory),
        )
        nuevos, duplicados, total, logs_msgs = result
        logger.info("Terminal raw pull completed", extra={"user": current_user.username, "action": "terminal_pull_manual"})
        return {"ok": True, "terminal_name": terminal.name, "total": total, "nuevos": nuevos, "duplicados": duplicados, "logs": logs_msgs[-200:], "warnings": pull_warnings(result)}
    except (TerminalOperationError, OSError, RuntimeError, ValueError) as exc:
        # run_pull ya dejó el error en la terminal.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{terminal_id}/pull/jobs", status_code=202)
def start_terminal_pull_job(
    terminal_id: int,
    background_tasks: BackgroundTasks,
    payload: TerminalPullRequest | None = None,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    terminal = get_terminal_or_404(terminal_id, db)
    if not terminal.is_active:
        raise HTTPException(status_code=400, detail="La terminal está inactiva")
    job = operation_status.create("terminal_pull", f"Descarga en cola: {terminal.name}")
    background_tasks.add_task(
        _run_terminal_pull_job,
        job["id"],
        terminal.id,
        current_user.username,
        bool(payload and payload.clear_device_memory),
    )
    return job


@router.get("/{terminal_id}/pull/jobs/{job_id}")
def get_terminal_pull_job(
    terminal_id: int,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    get_terminal_or_404(terminal_id, db)
    job = operation_status.get(job_id)
    if not job or job["operation"] != "terminal_pull":
        raise HTTPException(status_code=404, detail="Trabajo de descarga no encontrado")
    return job


@router.get("/{terminal_id}/device-users")
def list_device_users(
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    terminal = get_terminal_or_404(terminal_id, db)
    try:
        return service_list_terminal_users(terminal)
    except (TerminalOperationError, OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{terminal_id}/sync-user-names")
def sync_device_user_names(
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    terminal = get_terminal_or_404(terminal_id, db)
    try:
        result = service_sync_terminal_user_names(terminal, db)
        logger.info("Terminal user names synchronized", extra={"user": current_user.username, "action": "terminal_sync_user_names"})
        return ok_response(result)
    except (TerminalOperationError, OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{terminal_id}/pull-schedule")
def update_pull_schedule(
    terminal_id: int,
    payload: TerminalScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    terminal = get_terminal_or_404(terminal_id, db)
    try:
        apply_pull_schedule(
            terminal,
            enabled=payload.enabled,
            mode=payload.mode,
            interval_minutes=payload.interval_minutes,
            weekdays=payload.weekdays,
            scheduled_time=payload.scheduled_time,
            start_date=payload.start_date,
            end_date=payload.end_date,
            window_start=payload.window_start,
            window_end=payload.window_end,
        )
    except ScheduleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    logger.info("Terminal pull schedule updated", extra={"user": current_user.username, "action": "terminal_pull_schedule"})
    return ok_response({"enabled": terminal.pull_schedule_enabled, "next_pull_at": str(terminal.next_pull_at) if terminal.next_pull_at else None})
