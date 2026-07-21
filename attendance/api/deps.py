import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from core.database import SessionLocal
from models.user import AuthUser  # HR Admin
from core.security import ALGORITHM, JWT_AUDIENCE, JWT_ISSUER, SECRET_KEY

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token", auto_error=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = token or request.cookies.get("srtime_access_token")
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = db.query(AuthUser).filter(AuthUser.username == username).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    if int(payload.get("ver", 0)) != int(user.token_version or 0):
        raise credentials_exception
    return user


def require_root(current_user: AuthUser = Depends(get_current_user)):
    if current_user.role != "root":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Root role required",
        )
    return current_user


def require_supervisor_or_root(current_user: AuthUser = Depends(get_current_user)):
    if current_user.role not in ("root", "admin", "supervisor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor or root role required",
        )
    return current_user


# ── CRUD Helpers ───────────────────────────────────────────────

def get_or_404(db: Session, model, record_id: int, detail: str = "Record not found"):
    """Fetch a record by ID or raise 404."""
    record = db.query(model).filter(model.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=detail)
    return record


def update_from_dict(db_obj, data: dict, skip_none: bool = True):
    """Apply field-by-field updates from a dict, optionally skipping None values."""
    for key, value in data.items():
        if skip_none and value is None:
            continue
        setattr(db_obj, key, value)
    return db_obj


def ok_response(data: dict = None) -> dict:
    """Standard success response."""
    return {"ok": True, **(data or {})}



# ── Terminal helper ──────────────────────────────────────────────────────────

def get_terminal_or_404(terminal_id: int, db: Session):
    from models.terminal import DeviceTerminal
    return get_or_404(db, DeviceTerminal, terminal_id, detail="Terminal no encontrada")
