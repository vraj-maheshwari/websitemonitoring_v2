import logging
import smtplib
from email.message import EmailMessage

from app.config.settings import Config

logger = logging.getLogger(__name__)


def send_email(recipient: str, subject: str, body: str) -> None:
    if not Config.SMTP_HOST:
        raise RuntimeError("SMTP_HOST is not configured")

    message = EmailMessage()
    message["From"] = Config.SMTP_FROM_EMAIL
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=20) as smtp:
        if Config.SMTP_USE_TLS:
            smtp.starttls()
        if Config.SMTP_USERNAME:
            smtp.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
        smtp.send_message(message)

    logger.info("Email alert sent to %s", recipient)
