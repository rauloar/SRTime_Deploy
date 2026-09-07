from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db, require_supervisor_or_root
from core.logging_config import get_logger
from models.employee_group import EmployeeGroup
from models.shift import Shift
from models.user import AuthUser
from services.employee_groups import apply_group_shift, assign_users_to_group, create_group, list_groups, update_group

logger = get_logger(__name__)
router = APIRouter()


class EmployeeGroupBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    shift_id: Optional[int] = None
    is_active: bool = True


class EmployeeGroupCreate(EmployeeGroupBase):
    pass


class EmployeeGroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    shift_id: Optional[int] = None
    is_active: Optional[bool] = None


class EmployeeGroupResponse(EmployeeGroupBase):
    id: int
    employee_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class GroupAssignRequest(BaseModel):
    user_ids: list[int]
    override_manual: bool = False


class ApplyShiftRequest(BaseModel):
    include_manual: bool = False


def _get_group_or_404(group_id: int, db: Session) -> EmployeeGroup:
    group = db.query(EmployeeGroup).filter(EmployeeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo de empleados no encontrado")
    return group


def _validate_shift(shift_id: int | None, db: Session) -> None:
    if shift_id is None:
        return
    if not db.query(Shift.id).filter(Shift.id == shift_id).first():
        raise HTTPException(status_code=400, detail="El turno indicado no existe")


def _group_response(group: EmployeeGroup, employee_count: int = 0) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "shift_id": group.shift_id,
        "is_active": group.is_active,
        "employee_count": employee_count,
    }


@router.get("/", response_model=list[EmployeeGroupResponse])
def read_employee_groups(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return list_groups(db)


@router.post("/", response_model=EmployeeGroupResponse)
def create_employee_group(
    group: EmployeeGroupCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    _validate_shift(group.shift_id, db)
    try:
        created = create_group(
            db,
            name=group.name,
            description=group.description,
            shift_id=group.shift_id,
            is_active=group.is_active,
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Ya existe un grupo con ese nombre") from exc
    logger.info(
        "Employee group created",
        extra={"user": current_user.username, "action": "create_employee_group", "detail": created.name},
    )
    return _group_response(created)


@router.put("/{group_id}", response_model=EmployeeGroupResponse)
def update_employee_group(
    group_id: int,
    payload: EmployeeGroupUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    group = _get_group_or_404(group_id, db)
    if "shift_id" in payload.model_fields_set:
        _validate_shift(payload.shift_id, db)
    try:
        updated = update_group(
            db,
            group,
            name=payload.name,
            description=payload.description,
            update_description="description" in payload.model_fields_set,
            shift_id=payload.shift_id,
            update_shift="shift_id" in payload.model_fields_set,
            is_active=payload.is_active,
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Ya existe un grupo con ese nombre") from exc
    logger.info(
        "Employee group updated",
        extra={"user": current_user.username, "action": "update_employee_group", "detail": updated.name},
    )
    group_data = next((item for item in list_groups(db) if item["id"] == updated.id), None)
    return group_data or _group_response(updated)


@router.delete("/{group_id}")
def deactivate_employee_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    group = _get_group_or_404(group_id, db)
    group.is_active = False
    db.commit()
    logger.info(
        "Employee group deactivated",
        extra={"user": current_user.username, "action": "deactivate_employee_group", "detail": group.name},
    )
    return {"ok": True}


@router.post("/{group_id}/assign")
def assign_employee_group(
    group_id: int,
    payload: GroupAssignRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    group = _get_group_or_404(group_id, db)
    result = assign_users_to_group(
        db,
        group=group,
        user_ids=payload.user_ids,
        override_manual=payload.override_manual,
    )
    logger.info(
        "Employees assigned to group",
        extra={"user": current_user.username, "action": "assign_employee_group", "detail": group.name},
    )
    return {
        "assigned": result.assigned,
        "shift_updated": result.shift_updated,
        "manual_preserved": result.manual_preserved,
        "missing_users": result.missing_users,
    }


@router.post("/{group_id}/apply-shift")
def apply_employee_group_shift(
    group_id: int,
    payload: ApplyShiftRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    group = _get_group_or_404(group_id, db)
    result = apply_group_shift(db, group=group, include_manual=payload.include_manual)
    logger.info(
        "Employee group shift applied",
        extra={"user": current_user.username, "action": "apply_employee_group_shift", "detail": group.name},
    )
    return {
        "shift_updated": result.shift_updated,
        "manual_preserved": result.manual_preserved,
    }
