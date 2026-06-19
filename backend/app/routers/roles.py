from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
import datetime
import json

from ..auth import get_db, get_current_user
from ..db_models import DBRole, DBUser
from ..models import RoleCreate, RoleUpdate, RoleResponse

router = APIRouter(prefix="/roles", tags=["roles"])

def check_admin(current_user: DBUser, db: Session):
    role = db.query(DBRole).filter(DBRole.id == current_user.role_id).first()
    if not role or not role.permissions:
        raise HTTPException(status_code=403, detail="Sin permisos")
    perms = json.loads(role.permissions)
    if "manage_roles" not in perms:
        raise HTTPException(status_code=403, detail="No tienes permiso para gestionar roles")

@router.get("", response_model=List[RoleResponse])
def get_roles(db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    roles = db.query(DBRole).all()
    res = []
    for r in roles:
        res.append(RoleResponse(
            id=r.id,
            name=r.name,
            permissions=json.loads(r.permissions),
            allowed_areas=json.loads(r.allowed_areas) if r.allowed_areas else [],
            created_at=r.created_at
        ))
    return res

@router.post("", response_model=RoleResponse)
def create_role(role: RoleCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    existing = db.query(DBRole).filter(DBRole.name == role.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="El rol ya existe")
    
    role_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db_role = DBRole(
        id=role_id,
        name=role.name,
        permissions=json.dumps(role.permissions),
        allowed_areas=json.dumps(role.allowed_areas),
        created_at=now
    )
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return RoleResponse(
        id=db_role.id,
        name=db_role.name,
        permissions=json.loads(db_role.permissions),
        allowed_areas=json.loads(db_role.allowed_areas) if db_role.allowed_areas else [],
        created_at=db_role.created_at
    )

@router.put("/{role_id}", response_model=RoleResponse)
def update_role(role_id: str, role: RoleUpdate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    db_role = db.query(DBRole).filter(DBRole.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
        
    if role.name:
        existing = db.query(DBRole).filter(DBRole.name == role.name, DBRole.id != role_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="El nombre del rol ya está en uso")
        db_role.name = role.name
        
    if role.permissions is not None:
        db_role.permissions = json.dumps(role.permissions)
        
    if role.allowed_areas is not None:
        db_role.allowed_areas = json.dumps(role.allowed_areas)
        
    db.commit()
    db.refresh(db_role)
    return RoleResponse(
        id=db_role.id,
        name=db_role.name,
        permissions=json.loads(db_role.permissions),
        allowed_areas=json.loads(db_role.allowed_areas) if db_role.allowed_areas else [],
        created_at=db_role.created_at
    )

@router.delete("/{role_id}")
def delete_role(role_id: str, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    db_role = db.query(DBRole).filter(DBRole.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    
    users = db.query(DBUser).filter(DBUser.role_id == role_id).first()
    if users:
        raise HTTPException(status_code=400, detail="No se puede eliminar un rol que está asignado a usuarios")
        
    db.delete(db_role)
    db.commit()
    return {"message": "Rol eliminado"}
