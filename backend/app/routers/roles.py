from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
import datetime
import json

from ..auth import get_db, get_current_user
from ..db_models import DBRole, DBUser
from ..models import RoleAssignedUser, RoleCreate, RoleUpdate, RoleResponse

router = APIRouter(prefix="/roles", tags=["roles"])

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
        {"manage_roles"},
        "No tienes permiso para gestionar roles",
    )


def role_response(role: DBRole, db: Session) -> RoleResponse:
    assigned_users = (
        db.query(DBUser)
        .filter(DBUser.role_id == role.id)
        .order_by(DBUser.email.asc())
        .all()
    )
    return RoleResponse(
        id=role.id,
        name=role.name,
        permissions=json.loads(role.permissions),
        allowed_areas=json.loads(role.allowed_areas) if role.allowed_areas else [],
        created_at=role.created_at,
        user_count=len(assigned_users),
        assigned_users=[
            RoleAssignedUser(
                id=user.id,
                name=user.name,
                email=user.email,
                is_disabled=bool(user.is_disabled),
            )
            for user in assigned_users
        ],
    )


@router.get("", response_model=List[RoleResponse])
def get_roles(db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    require_any_permission(
        current_user,
        db,
        {"view_roles", "manage_roles", "manage_users"},
        "No tienes permiso para consultar roles",
    )
    roles = db.query(DBRole).order_by(DBRole.created_at.asc()).all()
    return [role_response(role, db) for role in roles]

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
    return role_response(db_role, db)

@router.put("/{role_id}", response_model=RoleResponse)
def update_role(role_id: str, role: RoleUpdate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    db_role = db.query(DBRole).filter(DBRole.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if db_role.name == "Super Admin":
        raise HTTPException(status_code=400, detail="No se puede modificar el rol Super Admin")
        
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
    return role_response(db_role, db)

@router.delete("/{role_id}")
def delete_role(role_id: str, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    check_admin(current_user, db)
    db_role = db.query(DBRole).filter(DBRole.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if db_role.name == "Super Admin":
        raise HTTPException(status_code=400, detail="No se puede eliminar el rol Super Admin")
    
    assigned_users = (
        db.query(DBUser)
        .filter(DBUser.role_id == role_id)
        .order_by(DBUser.email.asc())
        .all()
    )
    if assigned_users:
        user_list = ", ".join(
            f"{user.name or user.email} ({user.email})" for user in assigned_users
        )
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede eliminar un rol que está asignado a usuarios. "
                f"Usuarios asignados: {user_list}"
            ),
        )
        
    db.delete(db_role)
    db.commit()
    return {"message": "Rol eliminado"}
