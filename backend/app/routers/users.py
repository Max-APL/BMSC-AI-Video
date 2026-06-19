from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
import datetime
import json

from ..auth import get_db, get_current_user, get_password_hash
from ..db_models import DBUser, DBRole
from ..models import UserCreate, UserUpdate, UserResponse, RoleResponse

router = APIRouter(prefix="/users", tags=["users"])

def check_admin(current_user: DBUser, db: Session):
    role = db.query(DBRole).filter(DBRole.id == current_user.role_id).first()
    if not role or not role.permissions:
        raise HTTPException(status_code=403, detail="Sin permisos")
    perms = json.loads(role.permissions)
    if "manage_users" not in perms:
        raise HTTPException(status_code=403, detail="No tienes permiso para gestionar usuarios")

@router.get("", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    users = db.query(DBUser).all()
    res = []
    for u in users:
        role = db.query(DBRole).filter(DBRole.id == u.role_id).first()
        role_response = None
        if role:
            role_response = RoleResponse(
                id=role.id,
                name=role.name,
                permissions=json.loads(role.permissions),
                created_at=role.created_at
            )
        res.append(UserResponse(
            id=u.id,
            email=u.email,
            role_id=u.role_id,
            created_at=u.created_at,
            role=role_response
        ))
    return res

@router.post("", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    if not user.email.endswith("@bmsc.com.bo"):
        raise HTTPException(status_code=400, detail="El correo debe ser @bmsc.com.bo")
    
    existing = db.query(DBUser).filter(DBUser.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
        
    role = db.query(DBRole).filter(DBRole.id == user.role_id).first()
    if not role:
        raise HTTPException(status_code=400, detail="El rol especificado no existe")

    hashed_password = get_password_hash(user.password)
    user_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    
    db_user = DBUser(
        id=user_id,
        email=user.email,
        hashed_password=hashed_password,
        role_id=user.role_id,
        created_at=now
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse(
        id=db_user.id,
        email=db_user.email,
        role_id=db_user.role_id,
        created_at=db_user.created_at,
        role=RoleResponse(
            id=role.id,
            name=role.name,
            permissions=json.loads(role.permissions),
            created_at=role.created_at
        )
    )

@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: str, user: UserUpdate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    db_user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    if user.email:
        if not user.email.endswith("@bmsc.com.bo"):
            raise HTTPException(status_code=400, detail="El correo debe ser @bmsc.com.bo")
        existing = db.query(DBUser).filter(DBUser.email == user.email, DBUser.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="El correo ya está en uso")
        db_user.email = user.email
        
    if user.role_id:
        role = db.query(DBRole).filter(DBRole.id == user.role_id).first()
        if not role:
            raise HTTPException(status_code=400, detail="El rol especificado no existe")
        db_user.role_id = user.role_id
        
    if user.password:
        db_user.hashed_password = get_password_hash(user.password)
        
    db.commit()
    db.refresh(db_user)
    
    final_role = db.query(DBRole).filter(DBRole.id == db_user.role_id).first()
    return UserResponse(
        id=db_user.id,
        email=db_user.email,
        role_id=db_user.role_id,
        created_at=db_user.created_at,
        role=RoleResponse(
            id=final_role.id,
            name=final_role.name,
            permissions=json.loads(final_role.permissions),
            created_at=final_role.created_at
        ) if final_role else None
    )

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
