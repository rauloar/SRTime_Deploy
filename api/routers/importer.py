from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from models.user import AuthUser
from services.importer_service import import_att_logs

router = APIRouter()


@router.post("/txt")
async def import_txt_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    filename = (file.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in {".txt", ".bak"}:
        raise HTTPException(status_code=400, detail="Only .txt or .bak files are supported")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            tmp.write(content)
            temp_path = tmp.name

        nuevos, duplicados, total, logs_msgs = import_att_logs(temp_path, db, progress_signal=None)
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
