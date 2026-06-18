from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid
import datetime

from ..auth import create_access_token, verify_password, get_password_hash, get_db, get_current_user
from ..db_models import DBUser

router = APIRouter(prefix="/auth", tags=["auth"])

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    email: str
    password: str
    is_admin: bool = False

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

@router.post("/users")
def create_user(user: UserCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Solo administradores pueden crear usuarios")
    if not user.email.endswith("@bmsc.com.bo"):
        raise HTTPException(status_code=400, detail="El correo debe ser @bmsc.com.bo")
    
    existing = db.query(DBUser).filter(DBUser.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
        
    hashed_password = get_password_hash(user.password)
    user_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    
    db_user = DBUser(
        id=user_id,
        email=user.email,
        hashed_password=hashed_password,
        is_admin=user.is_admin,
        created_at=now
    )
    db.add(db_user)
    db.commit()
    return {"id": user_id, "email": user.email}
