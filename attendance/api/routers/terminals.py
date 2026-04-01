from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from api.deps import get_db, get_current_user
from models.user import AuthUser
from models.terminal import DeviceTerminal
from core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────

class TerminalCreate(BaseModel):
    name: str
    driver_name: str
    ip: str
    port: int = 4370
    password: str = "0"

class TerminalUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


# ── Helpers ──────────────────────────────────────────────────

def _get_terminal(terminal_id: int, db: Session) -> DeviceTerminal:
    terminal = db.query(DeviceTerminal).filter(DeviceTerminal.id == terminal_id).first()
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal no encontrada")
    return terminal


def _get_driver_instance(terminal: DeviceTerminal):
    """Instancia el driver correcto según driver_name de la terminal."""
    import services.addons
    info = services.addons.get_addon_info(terminal.driver_name)
    if not info or not info.get("is_driver"):
        raise HTTPException(status_code=400, detail=f"Driver '{terminal.driver_name}' no encontrado")
    return info["class"]()


def _get_connection_params(terminal: DeviceTerminal) -> dict:
    """Construye los params de conexión desde la BD."""
    return {
        "ip": terminal.ip,
        "port": str(terminal.port),
        "password": terminal.password or "0",
    }


# ── CRUD ─────────────────────────────────────────────────────

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
                "password": t.password,
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
    current_user: AuthUser = Depends(get_current_user),
):
    terminal = DeviceTerminal(
        name=payload.name,
        driver_name=payload.driver_name,
        ip=payload.ip,
        port=payload.port,
        password=payload.password,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)
    logger.info(f"Terminal created: {terminal.name} ({terminal.ip}:{terminal.port})",
                extra={"user": current_user.username, "action": "terminal_create"})
    return {"ok": True, "id": terminal.id}


@router.put("/{terminal_id}")
def update_terminal(
    terminal_id: int,
    payload: TerminalUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    terminal = _get_terminal(terminal_id, db)
    if payload.name is not None:
        terminal.name = payload.name
    if payload.ip is not None:
        terminal.ip = payload.ip
    if payload.port is not None:
        terminal.port = payload.port
    if payload.password is not None:
        terminal.password = payload.password
    if payload.is_active is not None:
        terminal.is_active = payload.is_active
    db.commit()
    logger.info(f"Terminal updated: {terminal.name}",
                extra={"user": current_user.username, "action": "terminal_update"})
    return {"ok": True}


@router.delete("/{terminal_id}")
def delete_terminal(
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    terminal = _get_terminal(terminal_id, db)
    name = terminal.name
    db.delete(terminal)
    db.commit()
    logger.info(f"Terminal deleted: {name}",
                extra={"user": current_user.username, "action": "terminal_delete"})
    return {"ok": True}


# ── Acciones (leen IP/puerto de la BD) ───────────────────────

@router.post("/{terminal_id}/test")
def test_terminal(
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    terminal = _get_terminal(terminal_id, db)
    driver = _get_driver_instance(terminal)
    params = _get_connection_params(terminal)

    try:
        result = driver.test_connection(params)

        # Guardar serial number en primer test exitoso
        sn = result.get("serial_number") or result.get("mac")
        if sn and not terminal.serial_number:
            terminal.serial_number = sn
            db.commit()

        logger.info(f"Terminal test OK: {terminal.name} ({terminal.ip})",
                    extra={"user": current_user.username, "action": "terminal_test"})
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{terminal_id}/sync")
def sync_terminal_time(
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    terminal = _get_terminal(terminal_id, db)
    driver = _get_driver_instance(terminal)
    params = _get_connection_params(terminal)

    try:
        ok = driver.sync_time(params)
        logger.info(f"Terminal sync: {terminal.name}",
                    extra={"user": current_user.username, "action": "terminal_sync"})
        return {"ok": ok}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{terminal_id}/import")
def import_from_terminal(
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    terminal = _get_terminal(terminal_id, db)
    driver = _get_driver_instance(terminal)
    params = _get_connection_params(terminal)

    from services.importer_service import import_from_driver
    logger.info(f"Terminal import started: {terminal.name} ({terminal.ip})",
                extra={"user": current_user.username, "action": "terminal_import"})

    nuevos, duplicados, total, logs_msgs = import_from_driver(driver, params, db, progress_signal=None)

    # Actualizar last_sync
    terminal.last_sync = datetime.now()
    db.commit()

    logger.info(f"Terminal import done: {terminal.name} → {nuevos} new, {duplicados} dup",
                extra={"user": current_user.username, "action": "terminal_import_done"})

    return {
        "ok": True,
        "terminal_name": terminal.name,
        "total": total,
        "nuevos": nuevos,
        "duplicados": duplicados,
        "logs": logs_msgs[-200:],
    }
