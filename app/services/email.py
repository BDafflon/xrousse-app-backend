import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def send_email(to: str, subject: str, html: str) -> None:
    """Send an email via Resend's HTTP API.

    This function must NEVER raise: any network error or non-2xx response
    from Resend is caught and logged, never propagated to the caller. This
    matters because alert-sending is called synchronously from inside
    request handlers (e.g. event publication) and must not break those
    flows if Resend is unavailable.
    """
    settings = get_settings()
    try:
        response = httpx.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.resend_from_email,
                "to": [to],
                "subject": subject,
                "html": html,
            },
        )
        response.raise_for_status()
    except Exception:
        logger.exception("Failed to send email to %s via Resend", to)
