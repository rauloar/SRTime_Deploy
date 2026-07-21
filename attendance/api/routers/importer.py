from pathlib import Path
import tempfile
import os

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user, get_terminal_or_404, require_supervisor_or_root
from models.user import AuthUser
from services.importer_service import import_att_logs
from services.terminals import TerminalOperationError, pull_logs
from core.limiter import limiter

router = APIRouter()


# ── Listado de addons disponibles ─────────────────────────────

@router.get("/parsers")
def list_parsers(current_user: AuthUser = Depends(get_current_user)):
    """Lista todos los addons disponibles: parsers de archivo y drivers de red."""
    import services.addons
    parsers = services.addons.get_available_parsers()
    res = []
    for name, info in parsers.items():
        res.append({
            "name": name,
            "is_driver": info["is_driver"],
            "is_parser": info["is_parser"],
            "connection_fields": info["connection_fields"],
        })
    return {"parsers": res}


# ── Ingesta desde archivo TXT ─────────────────────────────────

@router.post("/txt")
@limiter.limit("10/hour")
async def import_txt_file(
    request: Request,
    parser_name: str = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    """
    Ingesta Pull desde archivo TXT plano (upload manual o USB).
    Usa el parser de addon si se especifica, o el formato SRTime por defecto.
    """
    filename = (file.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    if suffix != ".txt":
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .txt")

    temp_path = None
    try:
        max_bytes = int(os.getenv("MAX_IMPORT_SIZE_BYTES", str(10 * 1024 * 1024)))
        bytes_written = 0
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            while chunk := await file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise HTTPException(status_code=413, detail="El archivo excede el límite permitido")
                tmp.write(chunk)
            if not bytes_written:
                raise HTTPException(status_code=400, detail="El archivo está vacío")
            temp_path = tmp.name

        import services.addons
        parser_instance = None
        if parser_name:
            parser_instance = services.addons.get_parser_instance(parser_name)
            if parser_instance is None:
                raise HTTPException(status_code=400, detail=f"Parser '{parser_name}' no encontrado")

        logger.info("File import started", extra={
            "user": current_user.username, "action": "import_txt", "detail": filename
        })
        nuevos, duplicados, total, logs_msgs = import_att_logs(
            temp_path,
            db,
            progress_signal=None,
            parser=parser_instance,
            source_label=filename,
        )
        logger.info(f"File import done: {nuevos} new, {duplicados} dup", extra={
            "user": current_user.username, "action": "import_txt_done"
        })
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
            Path(temp_path).unlink(missing_ok=True)


@router.post("/terminal/{terminal_id}/pull-logs")
@limiter.limit("10/minute")
def pull_logs_from_terminal(
    request: Request,
    terminal_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    terminal = get_terminal_or_404(terminal_id, db)

    logger.info(f"Pull logs started: {terminal.name} ({terminal.ip})", extra={
        "user": current_user.username, "action": "terminal_pull_logs"
    })

    try:
        nuevos, duplicados, total, logs_msgs = pull_logs(terminal, db)
    except (TerminalOperationError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(f"Pull logs done: {terminal.name} → {nuevos} new, {duplicados} dup", extra={
        "user": current_user.username, "action": "terminal_pull_logs_done"
    })

    return {
        "ok": True,
        "terminal_name": terminal.name,
        "total": total,
        "nuevos": nuevos,
        "duplicados": duplicados,
        "logs": logs_msgs[-200:],
    }
