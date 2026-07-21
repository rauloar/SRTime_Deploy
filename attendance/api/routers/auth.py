import os

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user
from core.limiter import limiter
from models.user import AuthUser
from core.security import create_access_token, hash_password as get_password_hash, validate_password, verify_password
from api.schemas import Token, PasswordChangeRequest, AuthMeResponse

router = APIRouter()

@router.post("/token", response_model=Token)
@limiter.limit("5/minute")
def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(AuthUser).filter(AuthUser.username == form_data.username).first()
    
    # Secure Password Verification
    if not user or not verify_password(form_data.password, user.password_hash):
        logger.warning("Login failed", extra={"user": form_data.username, "action": "login_failed"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
        
    access_token = create_access_token(data={"sub": user.username, "ver": user.token_version or 0})
    response.set_cookie(
        "srtime_access_token",
        access_token,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", str(request.url.scheme == "https")).lower() == "true",
        samesite="lax",
        max_age=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")) * 60,
        path="/",
    )
    logger.info("Login successful", extra={"user": user.username, "action": "login"})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "must_change_password": bool(user.must_change_password),
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("srtime_access_token", path="/")
    return {"ok": True}


@router.get("/me", response_model=AuthMeResponse)
def read_me(current_user: AuthUser = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role or "viewer",
        "is_active": bool(current_user.is_active),
        "must_change_password": bool(current_user.must_change_password),
    }


@router.post("/change-password")
def change_password(
    body: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    new_password = body.new_password.strip()
    try:
        validate_password(new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    must_change = bool(current_user.must_change_password)
    if not must_change:
        if not body.current_password:
            raise HTTPException(status_code=400, detail="Current password is required")
        if not verify_password(body.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.password_hash = get_password_hash(new_password)
    current_user.must_change_password = False
    current_user.token_version = int(current_user.token_version or 0) + 1
    db.commit()
    logger.info("Password changed", extra={"user": current_user.username, "action": "password_change"})
    return {"ok": True}
