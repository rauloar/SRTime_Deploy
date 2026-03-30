from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_db, require_root
from api.schemas import AuthUserResponse, AuthUserCreate, AuthUserUpdate
from api.security import get_password_hash
from models.user import AuthUser

router = APIRouter()

ALLOWED_ROLES = {"root", "admin", "supervisor", "viewer"}


@router.get("/", response_model=List[AuthUserResponse])
def read_auth_users(
    db: Session = Depends(get_db),
    _root_user: AuthUser = Depends(require_root),
):
    return db.query(AuthUser).order_by(AuthUser.username.asc()).all()


@router.post("/", response_model=AuthUserResponse)
def create_auth_user(
    body: AuthUserCreate,
    db: Session = Depends(get_db),
    _root_user: AuthUser = Depends(require_root),
):
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    role = body.role.strip().lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    existing = db.query(AuthUser).filter(AuthUser.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    rec = AuthUser(
        username=username,
        password_hash=get_password_hash(body.password),
        role=role,
        is_active=body.is_active,
        must_change_password=False,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.put("/{user_id}", response_model=AuthUserResponse)
def update_auth_user(
    user_id: int,
    body: AuthUserUpdate,
    db: Session = Depends(get_db),
    _root_user: AuthUser = Depends(require_root),
):
    rec = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="User not found")

    if body.username is not None:
        username = body.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username is required")
        dup = db.query(AuthUser).filter(AuthUser.username == username, AuthUser.id != user_id).first()
        if dup:
            raise HTTPException(status_code=400, detail="Username already exists")
        setattr(rec, "username", username)

    if body.role is not None:
        role = body.role.strip().lower()
        if role not in ALLOWED_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        setattr(rec, "role", role)

    if body.is_active is not None:
        setattr(rec, "is_active", body.is_active)

    if body.password:
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        setattr(rec, "password_hash", get_password_hash(body.password))
        setattr(rec, "must_change_password", False)

    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/{user_id}")
def delete_auth_user(
    user_id: int,
    db: Session = Depends(get_db),
    _root_user: AuthUser = Depends(require_root),
):
    rec = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="User not found")

    rec_role = str(getattr(rec, "role", ""))
    if rec_role == "root":
        root_count = db.query(AuthUser).filter(AuthUser.role == "root").count()
        if root_count <= 1:
            raise HTTPException(status_code=400, detail="At least one root account must remain")

    db.delete(rec)
    db.commit()
    return {"ok": True}
