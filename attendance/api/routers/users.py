from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user
from api.schemas import UserResponse, UserCreate
from models.employee import User as EmployeeModel
from models.user import AuthUser

router = APIRouter()

class UserUpdate(BaseModel):
    identifier: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    shift_id: Optional[int] = None

@router.get("/", response_model=List[UserResponse])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    users = db.query(EmployeeModel).offset(skip).limit(limit).all()
    return users

@router.get("/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    user = db.query(EmployeeModel).filter(EmployeeModel.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
    
@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    db_user = db.query(EmployeeModel).filter(EmployeeModel.identifier == user.identifier).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Identifier already registered")
    new_employee = EmployeeModel(
        identifier=user.identifier,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        shift_id=user.shift_id
    )
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)
    logger.info(f"Employee created: {user.identifier}", extra={"user": current_user.username, "action": "create_employee", "detail": user.identifier})
    return new_employee

@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
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
    if user.shift_id is not None: db_user.shift_id = user.shift_id
    else: db_user.shift_id = None  # Allow removing shift
    db.commit()
    db.refresh(db_user)
    logger.info(f"Employee updated: {db_user.identifier}", extra={"user": current_user.username, "action": "update_employee", "detail": db_user.identifier})
    return db_user

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    db_user = db.query(EmployeeModel).filter(EmployeeModel.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    logger.info(f"Employee deleted: {db_user.identifier}", extra={"user": current_user.username, "action": "delete_employee", "detail": db_user.identifier})
    return {"ok": True, "message": f"User {db_user.identifier} deleted"}
