"""Console/SMTP email delivery for auth tokens."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

BACKEND = os.getenv("ATLAS_EMAIL_BACKEND", "console")  # console | smtp
FROM_EMAIL = os.getenv("ATLAS_FROM_EMAIL", "atlas@localhost")


def send_email(to: str, subject: str, body: str) -> None:
    if BACKEND == "smtp":
        _send_smtp(to, subject, body)
    else:
        logger.info("Atlas email (console backend)\nTo: %s\nSubject: %s\n\n%s", to, subject, body)
        print(f"\n=== Atlas email to {to} ===\nSubject: {subject}\n{body}\n===\n")


def _send_smtp(to: str, subject: str, body: str) -> None:
    host = os.getenv("ATLAS_SMTP_HOST")
    port = int(os.getenv("ATLAS_SMTP_PORT", "587"))
    user = os.getenv("ATLAS_SMTP_USER")
    password = os.getenv("ATLAS_SMTP_PASSWORD")
    if not host:
        raise RuntimeError("ATLAS_SMTP_HOST required when ATLAS_EMAIL_BACKEND=smtp")

    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        if user and password:
            server.login(user, password)
        server.send_message(msg)
