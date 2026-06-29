from __future__ import annotations

from app.config import settings
from app.routers.users import _is_allowed_user_email


def test_user_email_domain_is_restricted_by_default():
    original = settings.allow_non_bmsc_emails
    try:
        object.__setattr__(settings, "allow_non_bmsc_emails", False)

        assert _is_allowed_user_email("user@bmsc.com.bo") is True
        assert _is_allowed_user_email("user@example.com") is False
    finally:
        object.__setattr__(settings, "allow_non_bmsc_emails", original)


def test_user_email_domain_can_be_relaxed_for_testing():
    original = settings.allow_non_bmsc_emails
    try:
        object.__setattr__(settings, "allow_non_bmsc_emails", True)

        assert _is_allowed_user_email("user@bmsc.com.bo") is True
        assert _is_allowed_user_email("user@example.com") is True
    finally:
        object.__setattr__(settings, "allow_non_bmsc_emails", original)
