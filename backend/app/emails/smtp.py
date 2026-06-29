from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.config import settings
from app.debug import log_event
from app.emails.messages import EmailContent
from app.emails.renderer import BRAND_NAME, LOGO_CID, LOGO_PATH


class EmailDeliveryError(RuntimeError):
    pass


def send_email(to_addr: str, content: EmailContent) -> None:
    if not settings.smtp_enabled:
        log_event(f"SMTP disabled; skipped email to={to_addr} subject={content.subject}")
        return
    if not settings.smtp_host or not settings.smtp_from:
        raise EmailDeliveryError("SMTP_HOST y SMTP_FROM deben estar configurados")

    message = EmailMessage()
    message["Subject"] = content.subject
    message["From"] = formataddr((BRAND_NAME, settings.smtp_from))
    message["To"] = to_addr
    message.set_content(content.body_plain)
    message.add_alternative(content.body_html, subtype="html")

    if LOGO_PATH.exists():
        with LOGO_PATH.open("rb") as logo_file:
            message.get_payload()[1].add_related(
                logo_file.read(),
                maintype="image",
                subtype="png",
                cid=f"<{LOGO_CID}>",
                filename=LOGO_PATH.name,
            )

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout,
        ) as smtp:
            smtp.send_message(message, from_addr=settings.smtp_from, to_addrs=[to_addr])
    except Exception as exc:
        raise EmailDeliveryError(f"No se pudo enviar el correo a {to_addr}") from exc
