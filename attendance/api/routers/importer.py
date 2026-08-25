from pathlib import Path
import tempfile
import os

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user, get_terminal_or_404, require_supervisor_or_root
from models.user import AuthUser
from services.importer_service import import_att_logs
from services.terminals import TerminalOperationError, pull_logs
from core.limiter import limiter
from core.database import SessionLocal
from core.operation_status import operation_status

router = APIRouter()


class _ImportProgress:
    def __init__(self, job_id: str, total: int):
        self.job_id = job_id
        self.total = total

    def emit(self, current: int, nuevos: int, duplicados: int, message: str) -> None:
        operation_status.update(
            self.job_id, current=current, total=self.total,
            message=f"{message} ({nuevos} nuevos, {duplicados} duplicados)",
        )


def _run_file_import(job_id: str, path: str, filename: str, parser_name: str | None, username: str, total: int) -> None:
    db = SessionLocal()
    try:
        import services.addons
        parser_instance = services.addons.get_parser_instance(parser_name) if parser_name else None
        if parser_name and parser_instance is None:
            raise RuntimeError(f"Parser '{parser_name}' no encontrado")
        progress = _ImportProgress(job_id, total)
        nuevos, duplicados, processed, logs_msgs = import_att_logs(
            path, db, progress_signal=progress, parser=parser_instance, source_label=filename,
        )
        result = {"filename": filename, "total": processed, "nuevos": nuevos, "duplicados": duplicados, "logs": logs_msgs[-200:]}
        operation_status.complete(job_id, result, f"Importación completada: {nuevos} nuevos, {duplicados} duplicados")
        logger.info("Background file import done", extra={"user": username, "action": "import_txt_done"})
    except Exception as exc:
        db.rollback()
        logger.exception("Background file import failed")
        operation_status.fail(job_id, f"Error al importar: {exc}")
    finally:
        db.close()
        Path(path).unlink(missing_ok=True)


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
            "capabilities": (info.get("manifest") or {}).get("capabilities") or {},
        })
    return {"parsers": res}


# ── Ingesta desde archivo TXT ─────────────────────────────────

@router.post("/txt/jobs", status_code=202)
@limiter.limit("10/hour")
async def start_import_txt_job(
    request: Request,
    background_tasks: BackgroundTasks,
    parser_name: str = None,
    file: UploadFile = File(...),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    """Queue file ingestion so the UI can show real progress while it runs."""
    filename = (file.filename or "").strip()
    if Path(filename).suffix.lower() != ".txt":
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .txt")
    max_bytes = int(os.getenv("MAX_IMPORT_SIZE_BYTES", str(10 * 1024 * 1024)))
    bytes_written = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        while chunk := await file.read(1024 * 1024):
            bytes_written += len(chunk)
            if bytes_written > max_bytes:
                Path(tmp.name).unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="El archivo excede el límite permitido")
            tmp.write(chunk)
        temp_path = tmp.name
    if not bytes_written:
        Path(temp_path).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    with open(temp_path, "r", encoding="latin-1") as uploaded:
        total = sum(1 for line in uploaded if line.strip())
    job = operation_status.create("import", f"Importación en cola: {filename}")
    operation_status.update(job["id"], current=0, total=total, message="Preparando importación")
    background_tasks.add_task(_run_file_import, job["id"], temp_path, filename, parser_name, current_user.username, total)
    return operation_status.get(job["id"])


@router.get("/jobs/{job_id}")
def get_import_job(job_id: str, current_user: AuthUser = Depends(get_current_user)):
    job = operation_status.get(job_id)
    if not job or job["operation"] != "import":
        raise HTTPException(status_code=404, detail="Import job not found")
    return job

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

    logger.info(f"Pull logs done: {terminal.name}: {nuevos} new, {duplicados} dup", extra={
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
