from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
import uuid
import datetime
import json

from ..auth import get_db, get_current_user, get_password_hash
from ..db_models import DBUser, DBRole
from ..models import UserCreate, UserUpdate, UserResponse, RoleResponse

router = APIRouter(prefix="/users", tags=["users"])

def require_any_permission(
    current_user: DBUser,
    db: Session,
    permissions: set[str],
    detail: str,
):
    role = db.query(DBRole).filter(DBRole.id == current_user.role_id).first()
    if not role or not role.permissions:
        raise HTTPException(status_code=403, detail="Sin permisos")
    perms = json.loads(role.permissions)
    if not permissions.intersection(perms):
        raise HTTPException(status_code=403, detail=detail)

def check_admin(current_user: DBUser, db: Session):
    require_any_permission(
        current_user,
        db,
        {"manage_users"},
        "No tienes permiso para gestionar usuarios",
    )


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def is_super_admin(db: Session, user: DBUser) -> bool:
    role = db.query(DBRole).filter(DBRole.id == user.role_id).first()
    return bool(role and role.name == "Super Admin")


def role_response(role: DBRole | None, db: Session) -> RoleResponse | None:
    if not role:
        return None
    return RoleResponse(
        id=role.id,
        name=role.name,
        permissions=json.loads(role.permissions),
        allowed_areas=json.loads(role.allowed_areas) if role.allowed_areas else [],
        created_at=role.created_at,
        user_count=db.query(DBUser).filter(DBUser.role_id == role.id).count(),
    )


def user_response(user: DBUser, db: Session) -> UserResponse:
    role = db.query(DBRole).filter(DBRole.id == user.role_id).first()
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role_id=user.role_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        is_disabled=bool(user.is_disabled),
        disabled_at=user.disabled_at,
        disabled_reason=user.disabled_reason,
        failed_login_attempts=user.failed_login_attempts or 0,
        role=role_response(role, db),
    )


@router.get("", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    require_any_permission(
        current_user,
        db,
        {"view_users", "manage_users"},
        "No tienes permiso para consultar usuarios",
    )
    users = db.query(DBUser).order_by(DBUser.created_at.desc()).all()
    return [user_response(user, db) for user in users]

@router.post("", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    email = str(user.email).strip().lower()
    if not email.endswith("@bmsc.com.bo"):
        raise HTTPException(status_code=400, detail="El correo debe ser @bmsc.com.bo")
    
    existing = db.query(DBUser).filter(func.lower(DBUser.email) == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
        
    role = db.query(DBRole).filter(DBRole.id == user.role_id).first()
    if not role:
        raise HTTPException(status_code=400, detail="El rol especificado no existe")

    hashed_password = get_password_hash(user.password)
    user_id = str(uuid.uuid4())
    now = now_iso()
    name = user.name.strip() if user.name and user.name.strip() else email.split("@")[0]
    
    db_user = DBUser(
        id=user_id,
        name=name,
        email=email,
        hashed_password=hashed_password,
        role_id=user.role_id,
        created_at=now,
        updated_at=now,
        is_disabled=False,
        failed_login_attempts=0,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return user_response(db_user, db)

@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: str, user: UserUpdate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    db_user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    if user.name is not None:
        name = user.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")
        db_user.name = name

    if user.email:
        email = str(user.email).strip().lower()
        if not email.endswith("@bmsc.com.bo"):
            raise HTTPException(status_code=400, detail="El correo debe ser @bmsc.com.bo")
        existing = db.query(DBUser).filter(
            func.lower(DBUser.email) == email,
            DBUser.id != user_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="El correo ya está en uso")
        db_user.email = email
        
    if user.role_id:
        role = db.query(DBRole).filter(DBRole.id == user.role_id).first()
        if not role:
            raise HTTPException(status_code=400, detail="El rol especificado no existe")
        if is_super_admin(db, db_user) and not is_super_admin(db, current_user):
            raise HTTPException(
                status_code=403,
                detail="Solo un Super Admin puede cambiar el rol de otro Super Admin",
            )
        db_user.role_id = user.role_id
        
    if user.password:
        db_user.hashed_password = get_password_hash(user.password)
        db_user.failed_login_attempts = 0

    if user.is_disabled is not None:
        if db_user.id == current_user.id and user.is_disabled:
            raise HTTPException(status_code=400, detail="No puedes deshabilitar tu propio usuario")
        if is_super_admin(db, db_user) and user.is_disabled and not is_super_admin(db, current_user):
            raise HTTPException(
                status_code=403,
                detail="Solo un Super Admin puede deshabilitar a otro Super Admin",
            )
        if db_user.is_disabled and not user.is_disabled and not is_super_admin(db, current_user):
            raise HTTPException(
                status_code=403,
                detail="Solo un Super Admin puede habilitar usuarios deshabilitados",
            )
        if user.is_disabled:
            db_user.is_disabled = True
            db_user.disabled_at = db_user.disabled_at or now_iso()
            db_user.disabled_reason = db_user.disabled_reason or "Deshabilitado manualmente"
        else:
            db_user.is_disabled = False
            db_user.disabled_at = None
            db_user.disabled_reason = None
            db_user.failed_login_attempts = 0

    db_user.updated_at = now_iso()
    db.commit()
    db.refresh(db_user)
    return user_response(db_user, db)

@router.delete("/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")
        
    db_user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    db.delete(db_user)
    db.commit()
    return {"message": "Usuario eliminado"}
