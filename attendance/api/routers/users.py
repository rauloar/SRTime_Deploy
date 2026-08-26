import csv
from io import StringIO
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user, require_root, require_supervisor_or_root
from api.schemas import UserResponse, UserCreate, UserBulkImportRow
from models.employee import TERMINAL_PRIVILEGE_ADMIN, TERMINAL_PRIVILEGE_USER, TERMINAL_PRIVILEGES, User as EmployeeModel
from models.shift import Shift
from models.user import AuthUser
from services.export_helpers import build_excel_workbook, streaming_excel_response

router = APIRouter()

class UserUpdate(BaseModel):
    identifier: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    shift_id: Optional[int] = None
    terminal_privilege: Optional[int] = None


def _terminal_privilege_label(value: int | None) -> str:
    return "ADMIN" if value == TERMINAL_PRIVILEGE_ADMIN else "USER"


def _parse_terminal_privilege(value: object) -> int:
    if value is None:
        return TERMINAL_PRIVILEGE_USER
    normalized = str(value).strip().upper()
    if not normalized:
        return TERMINAL_PRIVILEGE_USER
    if normalized in {"ADMIN", "ADMINISTRADOR", "14"}:
        return TERMINAL_PRIVILEGE_ADMIN
    if normalized in {"USER", "USUARIO", "0"}:
        return TERMINAL_PRIVILEGE_USER
    raise HTTPException(status_code=400, detail=f"Privilegio de terminal inválido: {value}")


def _parse_active(value: object) -> bool:
    if value is None:
        return True
    normalized = str(value).strip().lower()
    if not normalized:
        return True
    return normalized in {"si", "sí", "s", "yes", "y", "true", "1", "activo"}


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _resolve_shift_id(raw_value: str | None, shifts_by_name: dict[str, int]) -> int | None:
    value = (raw_value or "").strip()
    if not value or value.lower() in {"sin turno", "none", "null", "-"}:
        return None
    if value.isdigit():
        return int(value)
    return shifts_by_name.get(value.lower())

@router.get("/", response_model=List[UserResponse])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    users = db.query(EmployeeModel).offset(skip).limit(limit).all()
    return users

@router.get("/export")
def export_users(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    employees = db.query(EmployeeModel).order_by(EmployeeModel.last_name, EmployeeModel.first_name).all()
    shift_ids = {e.shift_id for e in employees if e.shift_id}
    shifts_by_id = {s.id: s.name for s in db.query(Shift).filter(Shift.id.in_(shift_ids)).all()} if shift_ids else {}

    headers = ["Identificador", "Nombre", "Apellido", "Turno", "Privilegio Terminal", "Activo"]
    data_rows = [
        [emp.identifier, emp.first_name or "", emp.last_name or "",
         shifts_by_id.get(emp.shift_id, "Sin turno"), _terminal_privilege_label(emp.terminal_privilege),
         "Sí" if emp.is_active else "No"]
        for emp in employees
    ]

    wb = build_excel_workbook("Empleados", headers, data_rows)
    return streaming_excel_response(wb, "empleados.xlsx")

@router.get("/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    user = db.query(EmployeeModel).filter(EmployeeModel.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
    
@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db), current_user: AuthUser = Depends(require_supervisor_or_root)):
    db_user = db.query(EmployeeModel).filter(EmployeeModel.identifier == user.identifier).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Identifier already registered")
    new_employee = EmployeeModel(
        identifier=user.identifier,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        shift_id=user.shift_id,
        terminal_privilege=user.terminal_privilege,
    )
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)
    logger.info(f"Employee created: {user.identifier}", extra={"user": current_user.username, "action": "create_employee", "detail": user.identifier})
    return new_employee

@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db), current_user: AuthUser = Depends(require_supervisor_or_root)):
    db_user = db.query(EmployeeModel).filter(EmployeeModel.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.identifier is not None:
        existing = db.query(EmployeeModel).filter(EmployeeModel.identifier == user.identifier, EmployeeModel.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Identifier already registered by another user")
        db_user.identifier = user.identifier
    if user.first_name is not None: db_user.first_name = user.first_name
    if user.last_name is not None: db_user.last_name = user.last_name
    if user.is_active is not None: db_user.is_active = user.is_active
    if "shift_id" in user.model_fields_set: db_user.shift_id = user.shift_id
    if user.terminal_privilege is not None:
        if user.terminal_privilege not in TERMINAL_PRIVILEGES:
            raise HTTPException(status_code=400, detail="terminal_privilege must be 0 (USER) or 14 (ADMIN)")
        db_user.terminal_privilege = user.terminal_privilege
    db.commit()
    db.refresh(db_user)
    logger.info(f"Employee updated: {db_user.identifier}", extra={"user": current_user.username, "action": "update_employee", "detail": db_user.identifier})
    return db_user

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(require_root)):
    db_user = db.query(EmployeeModel).filter(EmployeeModel.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    logger.info(f"Employee deleted: {db_user.identifier}", extra={"user": current_user.username, "action": "delete_employee", "detail": db_user.identifier})
    return {"ok": True, "message": f"User {db_user.identifier} deleted"}


@router.post("/bulk-import")
def bulk_import_users(
    users: List[UserBulkImportRow],
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root)
):
    created = skipped = 0
    for u in users:
        if db.query(EmployeeModel).filter_by(identifier=u.identifier).first():
            skipped += 1
            continue
        employee = EmployeeModel(
            identifier=u.identifier,
            first_name=u.first_name,
            last_name=u.last_name,
            is_active=u.is_active,
            shift_id=u.shift_id,
            terminal_privilege=u.terminal_privilege,
        )
        db.add(employee)
        created += 1
    db.commit()
    logger.info(f"Bulk import: {created} created, {skipped} skipped", extra={"user": current_user.username, "action": "bulk_import"})
    return {"created": created, "skipped": skipped}


@router.post("/import-csv")
async def import_users_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_supervisor_or_root),
):
    """Importa empleados desde el mismo CSV que exporta la UI.

    Formato soportado:
    Identificador, Nombre, Apellido, Turno, Privilegio Terminal, Activo

    La columna "Privilegio Terminal" es opcional para compatibilidad con
    archivos Sundial/legacy: si falta o viene vacía, se asume USER.
    """
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="El CSV debe estar codificado en UTF-8.") from exc

    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="El CSV no tiene encabezados.")
    header_map = {_normalize_header(name): name for name in reader.fieldnames}
    identifier_key = header_map.get("identificador") or header_map.get("identifier")
    if not identifier_key:
        raise HTTPException(status_code=400, detail="El CSV debe incluir la columna Identificador.")

    shifts_by_name = {shift.name.lower(): shift.id for shift in db.query(Shift).all()}
    created = updated = skipped = 0
    for row in reader:
        identifier = (row.get(identifier_key) or "").strip().zfill(15)
        if not identifier.strip("0"):
            skipped += 1
            continue

        first_name = row.get(header_map.get("nombre", ""), None)
        last_name = row.get(header_map.get("apellido", ""), None)
        shift_id = _resolve_shift_id(row.get(header_map.get("turno", ""), None), shifts_by_name)
        terminal_privilege = _parse_terminal_privilege(
            row.get(header_map.get("privilegio_terminal", ""), None)
            or row.get(header_map.get("terminal_privilege", ""), None)
        )
        is_active = _parse_active(row.get(header_map.get("activo", ""), None))

        employee = db.query(EmployeeModel).filter_by(identifier=identifier).first()
        if employee:
            employee.first_name = (first_name or "").strip() or None
            employee.last_name = (last_name or "").strip() or None
            employee.shift_id = shift_id
            employee.terminal_privilege = terminal_privilege
            employee.is_active = is_active
            updated += 1
        else:
            db.add(EmployeeModel(
                identifier=identifier,
                first_name=(first_name or "").strip() or None,
                last_name=(last_name or "").strip() or None,
                shift_id=shift_id,
                terminal_privilege=terminal_privilege,
                is_active=is_active,
            ))
            created += 1
    db.commit()
    logger.info(
        f"CSV employee import: {created} created, {updated} updated, {skipped} skipped",
        extra={"user": current_user.username, "action": "import_employees_csv"},
    )
    return {"created": created, "updated": updated, "skipped": skipped}
