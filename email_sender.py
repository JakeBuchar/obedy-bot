"""Minimal SMTP sender, configured entirely via environment variables so the
same code works locally and in GitHub Actions (secrets are injected as env
vars there).

Required env vars:
    SMTP_HOST       e.g. smtp.gmail.com / smtp.seznam.cz
    SMTP_USER       login for the SMTP account
    SMTP_PASSWORD   app password / SMTP password
    MAIL_TO         recipient address(es), comma-separated

Optional env vars:
    SMTP_PORT       default 465 (implicit TLS)
    MAIL_FROM       default = SMTP_USER
"""
from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(subject: str, html_body: str, text_body: str = "") -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    mail_from = os.environ.get("MAIL_FROM", user)
    recipients = [addr.strip() for addr in os.environ["MAIL_TO"].split(",") if addr.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(host, port) as server:
        server.login(user, password)
        server.sendmail(mail_from, recipients, msg.as_string())
