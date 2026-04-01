from pathlib import Path
import tempfile

from core.logging_config import get_logger
logger = get_logger(__name__)

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from models.user import AuthUser
from services.importer_service import import_att_logs

router = APIRouter()

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

@router.post("/device")
async def import_from_device(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    parser_name = payload.get("parser_name")
    params = payload.get("params", {})
    
    if not parser_name:
        raise HTTPException(status_code=400, detail="parser_name is required")
        
    import services.addons
    info = services.addons.get_addon_info(parser_name)
    if not info or not info.get("is_driver"):
        raise HTTPException(status_code=400, detail="Driver inválido o no encontrado")
        
    driver_instance = info["class"]()
    from services.importer_service import import_from_driver
    logger.info("Device import started", extra={"user": current_user.username, "action": "import_device", "detail": parser_name})
    nuevos, duplicados, total, logs_msgs = import_from_driver(driver_instance, params, db, progress_signal=None)
    logger.info(
        f"Device import completed: {nuevos} new, {duplicados} duplicates, {total} total",
        extra={"user": current_user.username, "action": "import_device_done", "detail": parser_name},
    )
    return {
        "ok": True,
        "total": total,
        "nuevos": nuevos,
        "duplicados": duplicados,
        "logs": logs_msgs[-200:],
    }


@router.post("/device/test")
async def test_device_connection(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    parser_name = payload.get("parser_name")
    params = payload.get("params", {})
    if not parser_name:
        raise HTTPException(status_code=400, detail="parser_name is required")
    import services.addons
    info = services.addons.get_addon_info(parser_name)
    if not info or not info.get("is_driver"):
        raise HTTPException(status_code=400, detail="Driver inválido")
    driver = info["class"]()
    try:
        res = driver.test_connection(params)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/device/sync")
async def sync_device_time(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    parser_name = payload.get("parser_name")
    params = payload.get("params", {})
    if not parser_name:
        raise HTTPException(status_code=400, detail="parser_name is required")
    import services.addons
    info = services.addons.get_addon_info(parser_name)
    if not info or not info.get("is_driver"):
        raise HTTPException(status_code=400, detail="Driver inválido")
    driver = info["class"]()
    try:
        ok = driver.sync_time(params)
        return {"ok": ok}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
