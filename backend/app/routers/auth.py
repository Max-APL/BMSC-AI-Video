import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
import datetime

from ..auth import (
    AUTH_PURPOSE_FIRST_LOGIN,
    AUTH_PURPOSE_PASSWORD_RESET,
    consume_auth_code,
    create_access_token,
    create_auth_code,
    get_db,
    get_current_user,
    get_password_hash,
    iso_now,
    is_user_locked,
    verify_password,
)
from ..config import settings
from ..debug import log_event
from ..db_models import DBUser, DBRole
from ..emails.messages import build_account_locked_email, build_password_reset_code_email, build_verification_code_email
from ..emails.smtp import EmailDeliveryError, send_email
from ..models import FirstLoginCompleteRequest, LoginRequest, PasswordResetConfirmRequest, PasswordResetRequest

router = APIRouter(prefix="/auth", tags=["auth"])

class Token(BaseModel):
    access_token: str | None = None
    token_type: str
    status: str = "ok"
    email: str | None = None
    detail: str | None = None
    code_expires_minutes: int | None = None
    locked_until: str | None = None


def _token_for_user(user: DBUser) -> Token:
    access_token = create_access_token(
        data={"sub": user.id, "token_version": int(user.token_version or 0)}
    )
    return Token(access_token=access_token, token_type="bearer")


def _send_first_login_code(db: Session, user: DBUser) -> Token:
    code = create_auth_code(db, user, AUTH_PURPOSE_FIRST_LOGIN)
    send_email(
        user.email,
        build_verification_code_email(
            username=user.email,
            code=code,
            expires_minutes=settings.auth_code_expire_minutes,
        ),
    )
    db.commit()
    return Token(
        token_type="bearer",
        status="password_change_required",
        email=user.email,
        detail="Debes cambiar tu contraseña temporal. Te enviamos un código de verificación.",
        code_expires_minutes=settings.auth_code_expire_minutes,
    )


def _register_failed_login(db: Session, user: DBUser) -> None:
    user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= settings.auth_max_failed_login_attempts:
        user.locked_until = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=settings.auth_lockout_minutes)
        ).isoformat()
        try:
            send_email(
                user.email,
                build_account_locked_email(
                    username=user.email,
                    lockout_minutes=settings.auth_lockout_minutes,
                ),
            )
        except EmailDeliveryError as exc:
            log_event(f"Account lock email failed user={user.email} error={exc}")
    db.commit()


def _login(email: str, password: str, db: Session) -> Token:
    user = db.query(DBUser).filter(DBUser.email == email).first()
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

    if is_user_locked(user):
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "status": "locked",
                "message": "Cuenta bloqueada temporalmente",
                "locked_until": user.locked_until,
            },
        )
    if not verify_password(password, user.hashed_password):
        _register_failed_login(db, user)
        if user.locked_until:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "status": "locked",
                    "message": "Cuenta bloqueada temporalmente",
                    "locked_until": user.locked_until,
                },
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    if user.force_password_change:
        try:
            return _send_first_login_code(db, user)
        except EmailDeliveryError as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    db.commit()
    return _token_for_user(user)


@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(form_data.username, form_data.password, db)

@router.post("/login", response_model=Token)
def login_json(request: LoginRequest, db: Session = Depends(get_db)):
    return _login(request.email, request.password, db)


@router.post("/first-login/complete", response_model=Token)
def complete_first_login(request: FirstLoginCompleteRequest, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.email == request.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Código inválido o expirado")
    consume_auth_code(db, user, AUTH_PURPOSE_FIRST_LOGIN, request.code)
    user.hashed_password = get_password_hash(request.new_password)
    user.force_password_change = False
    user.password_changed_at = iso_now()
    user.failed_login_attempts = 0
    user.locked_until = None
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    return _token_for_user(user)


@router.post("/password-reset/request")
def request_password_reset(request: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.email == request.email).first()
    if user:
        try:
            code = create_auth_code(db, user, AUTH_PURPOSE_PASSWORD_RESET)
            send_email(
                user.email,
                build_password_reset_code_email(
                    username=user.email,
                    code=code,
                    expires_minutes=settings.auth_code_expire_minutes,
                ),
            )
            db.commit()
        except EmailDeliveryError as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"message": "Si el correo existe, enviaremos un código de recuperación."}


@router.post("/password-reset/confirm", response_model=Token)
def confirm_password_reset(request: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.email == request.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Código inválido o expirado")
    consume_auth_code(db, user, AUTH_PURPOSE_PASSWORD_RESET, request.code)
    user.hashed_password = get_password_hash(request.new_password)
    user.force_password_change = False
    user.password_changed_at = iso_now()
    user.failed_login_attempts = 0
    user.locked_until = None
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    return _token_for_user(user)

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
        "force_password_change": bool(current_user.force_password_change),
        "locked_until": current_user.locked_until,
    }
