import logging

import httpx

from app.config.settings import Config

logger = logging.getLogger(__name__)


def send_teams_alert(subject: str, body: str) -> None:
    if not Config.TEAMS_WEBHOOK_URL:
        raise RuntimeError("TEAMS_WEBHOOK_URL is not configured")

    payload = {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "Website Alert",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": "TextBlock",
                "text": subject,
                "weight": "Bolder",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": body,
                "wrap": True,
            },
        ],
    }

    response = httpx.post(Config.TEAMS_WEBHOOK_URL, json=payload, timeout=20)
    response.raise_for_status()
    logger.info("Teams alert sent: %s", subject)
