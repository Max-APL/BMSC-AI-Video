from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import uuid
import datetime

from ..auth import get_db, get_current_user, require_permission
from ..db_models import DBArea, DBSubArea, DBUser, DBVideoMetadata

router = APIRouter(prefix="/areas", tags=["areas"])

class SubAreaResponse(BaseModel):
    id: str
    name: str
    area_id: str

class AreaResponse(BaseModel):
    id: str
    name: str
    subareas: List[SubAreaResponse]

class AreaCreate(BaseModel):
    name: str

class SubAreaCreate(BaseModel):
    name: str

@router.get("", response_model=List[AreaResponse])
def get_areas(db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    from ..db_models import DBRole
    import json
    role = db.query(DBRole).filter(DBRole.id == current_user.role_id).first()
    allowed_areas = json.loads(role.allowed_areas) if role and role.allowed_areas else []
    
    areas = db.query(DBArea).all()
    result = []
    for area in areas:
        if "*" not in allowed_areas and area.id not in allowed_areas:
            continue
            
        subareas = db.query(DBSubArea).filter(DBSubArea.area_id == area.id).all()
        result.append({
            "id": area.id,
            "name": area.name,
            "subareas": [{"id": s.id, "name": s.name, "area_id": s.area_id} for s in subareas]
        })
    return result

@router.post("", response_model=AreaResponse)
def create_area(area: AreaCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(require_permission("manage_organization"))):
    new_id = str(uuid.uuid4())
    db_area = DBArea(
        id=new_id,
        name=area.name,
        created_at=datetime.datetime.utcnow().isoformat()
    )
    db.add(db_area)
    db.commit()
    return {"id": new_id, "name": area.name, "subareas": []}

@router.post("/{area_id}/subareas", response_model=SubAreaResponse)
def create_subarea(area_id: str, subarea: SubAreaCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(require_permission("manage_organization"))):
    area = db.query(DBArea).filter(DBArea.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
        
    new_id = str(uuid.uuid4())
    db_subarea = DBSubArea(
        id=new_id,
        name=subarea.name,
        area_id=area_id,
        created_at=datetime.datetime.utcnow().isoformat()
    )
    db.add(db_subarea)
    db.commit()
    return {"id": new_id, "name": subarea.name, "area_id": area_id}

@router.put("/videos/{video_id}/subarea")
def assign_video_subarea(video_id: str, subarea_id: Optional[str] = None, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    video = db.query(DBVideoMetadata).filter(DBVideoMetadata.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    
    if subarea_id:
        subarea = db.query(DBSubArea).filter(DBSubArea.id == subarea_id).first()
        if not subarea:
            raise HTTPException(status_code=404, detail="Subárea no encontrada")
            
    video.subarea_id = subarea_id
    db.commit()
    return {"status": "ok"}
