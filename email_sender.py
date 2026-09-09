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
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(
    subject: str,
    html_body: str,
    text_body: str = "",
    inline_images: dict[str, bytes] | None = None,
) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    mail_from = os.environ.get("MAIL_FROM", user)
    recipients = [addr.strip() for addr in os.environ.get("MAIL_TO", "").split(",") if addr.strip()]
    # An unset secret arrives as an empty string, so without this the run
    # would get all the way to SMTP and fail there with "recipients refused".
    if not recipients:
        raise ValueError(
            "MAIL_TO is empty - set the recipient secret for this city "
            "(MAIL_TO for Praha, MAIL_TO_KOLIN for Kolín)"
        )

    body = MIMEMultipart("alternative")
    if text_body:
        body.attach(MIMEText(text_body, "plain", "utf-8"))
    body.attach(MIMEText(html_body, "html", "utf-8"))

    # Images referenced as cid: have to sit next to the body in a
    # multipart/related container, otherwise clients treat them as plain
    # attachments and the <img> tags stay empty.
    if inline_images:
        msg = MIMEMultipart("related")
        msg.attach(body)
        for content_id, data in inline_images.items():
            image = MIMEImage(data, "png")
            image.add_header("Content-ID", f"<{content_id}>")
            image.add_header("Content-Disposition", "inline", filename=f"{content_id}.png")
            msg.attach(image)
    else:
        msg = body

    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)

    with smtplib.SMTP_SSL(host, port) as server:
        server.login(user, password)
        server.sendmail(mail_from, recipients, msg.as_string())
