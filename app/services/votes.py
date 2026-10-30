import hashlib
import hmac
import secrets

from fastapi import Request, Response

from app.config import get_settings

ANON_COOKIE_NAME = "rcx_anon_id"
_ANON_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365 * 5  # 5 years


def _sign(value: str) -> str:
    settings = get_settings()
    signature = hmac.new(
        settings.jwt_secret_key.encode(), value.encode(), hashlib.sha256
    ).hexdigest()
    return f"{value}.{signature}"


def _verify(signed_value: str) -> str | None:
    try:
        value, signature = signed_value.rsplit(".", 1)
    except ValueError:
        return None

    settings = get_settings()
    expected_signature = hmac.new(
        settings.jwt_secret_key.encode(), value.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None
    return value


def get_or_create_anon_id(request: Request, response: Response) -> str:
    cookie_value = request.cookies.get(ANON_COOKIE_NAME)
    if cookie_value:
        anon_id = _verify(cookie_value)
        if anon_id:
            return anon_id

    anon_id = secrets.token_urlsafe(32)
    response.set_cookie(
        key=ANON_COOKIE_NAME,
        value=_sign(anon_id),
        max_age=_ANON_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return anon_id
