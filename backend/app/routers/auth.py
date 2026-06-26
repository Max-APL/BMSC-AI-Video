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

MAX_LOGIN_ATTEMPTS = 5


def _is_super_admin(role: DBRole | None) -> bool:
    return bool(role and role.name == "Super Admin")


def _authenticate_user(email: str, password: str, db: Session):
    user = db.query(DBUser).filter(DBUser.email == email).first()
    role = db.query(DBRole).filter(DBRole.id == user.role_id).first() if user else None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.is_disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario deshabilitado. Solicita la habilitación a un Super Admin.",
        )

    if not verify_password(password, user.hashed_password):
        if not _is_super_admin(role):
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                user.is_disabled = True
                user.disabled_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                user.disabled_reason = "Bloqueado por superar 5 intentos fallidos de inicio de sesión"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Usuario deshabilitado por superar 5 intentos fallidos. Solicita la habilitación a un Super Admin.",
                )
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.failed_login_attempts:
        user.failed_login_attempts = 0
        db.commit()

    return user


@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = _authenticate_user(form_data.username, form_data.password, db)
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
def login_json(request: LoginRequest, db: Session = Depends(get_db)):
    user = _authenticate_user(request.email, request.password, db)
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
        "name": current_user.name,
        "email": current_user.email,
        "role": role.name if role else "Unknown",
        "permissions": permissions,
        "allowed_areas": allowed_areas,
        "is_disabled": current_user.is_disabled,
        "failed_login_attempts": current_user.failed_login_attempts or 0,
    }
