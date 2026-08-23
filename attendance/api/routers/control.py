"""Root-only operational endpoints used by the local Control Center."""
from fastapi import APIRouter, Depends, HTTPException

from api.deps import require_root
from services.operations import create_postgres_backup, get_status

router = APIRouter()


@router.get("/status")
def control_status(_current_user=Depends(require_root)):
    return get_status()


@router.post("/backups")
def create_backup(_current_user=Depends(require_root)):
    try:
        return {"ok": True, "backup": create_postgres_backup()}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
