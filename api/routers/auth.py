from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from models.user import AuthUser
from api.security import verify_password, create_access_token, get_password_hash
from api.schemas import Token, PasswordChangeRequest, AuthMeResponse

router = APIRouter()

@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(AuthUser).filter(AuthUser.username == form_data.username).first()
    
    # Secure Password Verification
    if not user or not verify_password(form_data.password, user.password_hash):
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
        
    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "must_change_password": bool(user.must_change_password),
    }


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
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    must_change = bool(current_user.must_change_password)
    if not must_change:
        if not body.current_password:
            raise HTTPException(status_code=400, detail="Current password is required")
        if not verify_password(body.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.password_hash = get_password_hash(new_password)
    current_user.must_change_password = False
    db.commit()
    return {"ok": True}
