import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid
import datetime

from ..auth import create_access_token, verify_password, get_password_hash, get_db, get_current_user
from ..db_models import DBUser, DBRole
from ..models import LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
def login_json(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
def read_users_me(current_user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    role = db.query(DBRole).filter(DBRole.id == current_user.role_id).first()
    permissions = []
    allowed_areas = []
    if role:
        if role.permissions:
            permissions = json.loads(role.permissions)
        if role.allowed_areas:
            allowed_areas = json.loads(role.allowed_areas)
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": role.name if role else "Unknown",
        "permissions": permissions,
        "allowed_areas": allowed_areas
    }
