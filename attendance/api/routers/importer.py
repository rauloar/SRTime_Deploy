from pathlib import Path
import tempfile

from core.logging_config import get_logger
logger = get_logger(__name__)

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from models.user import AuthUser
from models.terminal import DeviceTerminal
from services.importer_service import import_att_logs
from datetime import datetime

router = APIRouter()

def _get_driver_and_params(terminal: DeviceTerminal):
    import services.addons
    info = services.addons.get_addon_info(terminal.driver_name)
    if not info or not info.get("is_driver"):
        raise HTTPException(status_code=400, detail=f"Driver '{terminal.driver_name}' no encontrado")
    driver = info["class"]()
    params = {"ip": terminal.ip, "port": str(terminal.port), "password": terminal.password or "0"}
    return driver, params

@router.get("/parsers")
def list_parsers():
    import services.addons
    parsers = services.addons.get_available_parsers()
    res = []
    for name, info in parsers.items():
        res.append({
            "name": name,
            "is_driver": info["is_driver"],
            "connection_fields": info["connection_fields"]
        })
    return {"parsers": res}

@router.post("/device/{terminal_id}")
async def import_from_terminal_db(
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    terminal = db.query(DeviceTerminal).filter(DeviceTerminal.id == terminal_id).first()
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal no encontrada")
        
    driver, params = _get_driver_and_params(terminal)

    from services.importer_service import import_from_driver
    logger.info(f"Terminal import started: {terminal.name} ({terminal.ip})",
                extra={"user": current_user.username, "action": "terminal_import"})

    nuevos, duplicados, total, logs_msgs = import_from_driver(driver, params, db, progress_signal=None)

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

@router.post("/txt")
async def import_txt_file(
    parser_name: str = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    filename = (file.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    if suffix != ".txt":
        raise HTTPException(status_code=400, detail="Only .txt files are supported")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            tmp.write(content)
            temp_path = tmp.name

        import services.addons
        parser_instance = None
        if parser_name:
            parser_instance = services.addons.get_parser_instance(parser_name)

        logger.info("File import started", extra={"user": current_user.username, "action": "import_txt", "detail": filename})
        nuevos, duplicados, total, logs_msgs = import_att_logs(temp_path, db, progress_signal=None, parser=parser_instance)
        logger.info(
            f"File import completed: {nuevos} new, {duplicados} duplicates, {total} total",
            extra={"user": current_user.username, "action": "import_txt_done", "detail": filename},
        )
        return {
            "ok": True,
            "filename": filename,
            "total": total,
            "nuevos": nuevos,
            "duplicados": duplicados,
            "logs": logs_msgs[-200:],
        }
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass
