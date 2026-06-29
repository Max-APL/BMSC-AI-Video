import jwt
import bcrypt
import datetime
import hashlib
import secrets
import string
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .database import SessionLocal
from .db_models import DBAuthCode, DBUser
from .config import settings

ALGORITHM = "HS256"
AUTH_PURPOSE_FIRST_LOGIN = "first_login"
AUTH_PURPOSE_PASSWORD_RESET = "password_reset"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = utc_now() + datetime.timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_datetime(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def is_user_locked(user: DBUser) -> bool:
    locked_until = parse_datetime(user.locked_until)
    if not locked_until:
        return False
    if locked_until <= utc_now():
        user.locked_until = None
        user.failed_login_attempts = 0
        return False
    return True


def create_random_code(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def create_temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(ch.islower() for ch in password)
            and any(ch.isupper() for ch in password)
            and any(ch.isdigit() for ch in password)
        ):
            return password


def hash_auth_code(code: str, purpose: str) -> str:
    payload = f"{settings.jwt_secret_key}:{purpose}:{code}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def create_auth_code(db: Session, user: DBUser, purpose: str) -> str:
    import uuid

    now = utc_now()
    db.query(DBAuthCode).filter(
        DBAuthCode.user_id == user.id,
        DBAuthCode.purpose == purpose,
        DBAuthCode.consumed_at.is_(None),
    ).update({"consumed_at": now.isoformat()})
    code = create_random_code()
    db.add(
        DBAuthCode(
            id=str(uuid.uuid4()),
            user_id=user.id,
            purpose=purpose,
            code_hash=hash_auth_code(code, purpose),
            expires_at=(now + datetime.timedelta(minutes=settings.auth_code_expire_minutes)).isoformat(),
            attempts=0,
            consumed_at=None,
            created_at=now.isoformat(),
        )
    )
    return code


def consume_auth_code(db: Session, user: DBUser, purpose: str, code: str) -> None:
    auth_code = (
        db.query(DBAuthCode)
        .filter(
            DBAuthCode.user_id == user.id,
            DBAuthCode.purpose == purpose,
            DBAuthCode.consumed_at.is_(None),
        )
        .order_by(DBAuthCode.created_at.desc())
        .first()
    )
    if not auth_code:
        raise HTTPException(status_code=400, detail="Código inválido o expirado")

    expires_at = parse_datetime(auth_code.expires_at)
    if not expires_at or expires_at <= utc_now():
        auth_code.consumed_at = iso_now()
        raise HTTPException(status_code=400, detail="Código inválido o expirado")

    if auth_code.attempts >= settings.auth_code_max_attempts:
        auth_code.consumed_at = iso_now()
        raise HTTPException(status_code=400, detail="Código inválido o expirado")

    if auth_code.code_hash != hash_auth_code(code.strip(), purpose):
        auth_code.attempts += 1
        raise HTTPException(status_code=400, detail="Código inválido o expirado")

    auth_code.consumed_at = iso_now()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_version = payload.get("token_version", 0)
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if user is None:
        raise credentials_exception
    if user.is_disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario deshabilitado. Solicita la habilitación a un Super Admin.",
        )
    if int(user.token_version or 0) != int(token_version or 0):
        raise credentials_exception
    locked_until_before = user.locked_until
    if is_user_locked(user):
        db.commit()
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Cuenta bloqueada temporalmente")
    if locked_until_before and not user.locked_until:
        db.commit()
    return user

def require_permission(permission: str):
    def dependency(current_user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
        from .db_models import DBRole
        import json
        role = db.query(DBRole).filter(DBRole.id == current_user.role_id).first()
        if not role or not role.permissions:
            raise HTTPException(status_code=403, detail="Sin permisos")
        perms = json.loads(role.permissions)
        if permission not in perms:
            raise HTTPException(status_code=403, detail=f"Falta el permiso: {permission}")
        return current_user
    return dependency
