from __future__ import annotations

import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import (
    AUTH_PURPOSE_PASSWORD_RESET,
    consume_auth_code,
    create_auth_code,
    get_password_hash,
    is_user_locked,
    utc_now,
)
from app.config import settings
from app.db_models import Base, DBRole, DBUser
from app.emails.messages import build_password_reset_code_email
from app.emails.smtp import send_email


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        role = DBRole(
            id="role-1",
            name="Super Admin",
            permissions="[]",
            allowed_areas="[]",
            created_at=utc_now().isoformat(),
        )
        user = DBUser(
            id="user-1",
            email="user@bmsc.com.bo",
            hashed_password=get_password_hash("Temporal123"),
            role_id=role.id,
            created_at=utc_now().isoformat(),
            failed_login_attempts=0,
            locked_until=None,
            force_password_change=True,
            password_changed_at=None,
            token_version=0,
        )
        db.add(role)
        db.add(user)
        db.commit()
        yield db
    finally:
        db.close()


def test_email_templates_use_ai_video_brand():
    email = build_password_reset_code_email("user@bmsc.com.bo", "123456", 15)

    assert "AI Video" in email.subject
    assert "AI Video" in email.body_html
    assert "AI Video" in email.body_plain
    assert "Base de Conocimiento" not in email.body_html
    assert "Base de Conocimiento" not in email.body_plain


def test_auth_code_can_only_be_consumed_once(db_session):
    user = db_session.query(DBUser).filter(DBUser.id == "user-1").one()
    code = create_auth_code(db_session, user, AUTH_PURPOSE_PASSWORD_RESET)
    db_session.commit()

    consume_auth_code(db_session, user, AUTH_PURPOSE_PASSWORD_RESET, code)
    db_session.commit()

    with pytest.raises(HTTPException):
        consume_auth_code(db_session, user, AUTH_PURPOSE_PASSWORD_RESET, code)


def test_expired_lock_clears_user_state(db_session):
    user = db_session.query(DBUser).filter(DBUser.id == "user-1").one()
    user.failed_login_attempts = 5
    user.locked_until = (utc_now() - datetime.timedelta(minutes=1)).isoformat()

    assert is_user_locked(user) is False
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


def test_send_email_uses_configured_smtp(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent["host"] = host
            sent["port"] = port
            sent["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def send_message(self, message, from_addr=None, to_addrs=None):
            sent["to"] = message["To"]
            sent["subject"] = message["Subject"]
            sent["from_addr"] = from_addr
            sent["to_addrs"] = to_addrs

    monkeypatch.setattr("app.emails.smtp.smtplib.SMTP", FakeSMTP)
    original = {
        "smtp_enabled": settings.smtp_enabled,
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_from": settings.smtp_from,
        "smtp_timeout": settings.smtp_timeout,
    }
    try:
        object.__setattr__(settings, "smtp_enabled", True)
        object.__setattr__(settings, "smtp_host", "localhost")
        object.__setattr__(settings, "smtp_port", 1025)
        object.__setattr__(settings, "smtp_from", "no-reply@bmsc.local")
        object.__setattr__(settings, "smtp_timeout", 10)

        send_email(
            "user@bmsc.com.bo",
            build_password_reset_code_email("user@bmsc.com.bo", "123456", 15),
        )
    finally:
        for key, value in original.items():
            object.__setattr__(settings, key, value)

    assert sent["host"] == "localhost"
    assert sent["port"] == 1025
    assert sent["timeout"] == 10
    assert sent["to"] == "user@bmsc.com.bo"
    assert sent["from_addr"] == "no-reply@bmsc.local"
    assert sent["to_addrs"] == ["user@bmsc.com.bo"]
    assert "AI Video" in sent["subject"]
