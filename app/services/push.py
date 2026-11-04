import base64
import json
import logging
import os
from functools import lru_cache

from sqlmodel import Session, select

from app.config import get_settings
from app.models.push_token import PushToken
from app.models.user import User

logger = logging.getLogger(__name__)


@lru_cache
def _firebase_app():
    """Lazily initialised Firebase Admin app, or None when push isn't
    configured (FIREBASE_CREDENTIALS_JSON unset/invalid) — push is then a
    silent no-op and everything else keeps working."""
    raw = get_settings().firebase_credentials_json
    if not raw:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials

        raw = raw.strip()
        if not raw.startswith("{"):
            if os.path.isfile(raw):  # path to the service-account JSON file
                with open(raw) as f:
                    raw = f.read()
            else:
                raw = base64.b64decode(raw).decode()
        return firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))
    except Exception:
        logger.exception("Invalid FIREBASE_CREDENTIALS_JSON, push disabled")
        return None


def _build_message(token: PushToken, title: str, body: str, link: str | None):
    from firebase_admin import messaging

    data = {"title": title, "body": body, "link": link or "/"}
    if token.platform == "web":
        # Data-only: the service worker decides whether to show a system
        # notification or just refresh the open tab (see public/push-sw.js).
        return messaging.Message(
            token=token.token,
            data=data,
            webpush=messaging.WebpushConfig(headers={"Urgency": "high"}),
        )
    return messaging.Message(
        token=token.token,
        notification=messaging.Notification(title=title, body=body),
        data=data,
        android=messaging.AndroidConfig(priority="high"),
        apns=messaging.APNSConfig(
            headers={"apns-priority": "10"},
            payload=messaging.APNSPayload(aps=messaging.Aps(sound="default")),
        ),
    )


def send_push(session: Session, user: User, title: str, body: str, link: str | None) -> None:
    """Push `title`/`body` to every registered device of `user`.

    Never raises. Tokens FCM reports as unregistered/invalid are deleted.
    """
    try:
        app = _firebase_app()
        if app is None:
            return
        from firebase_admin import exceptions, messaging

        tokens = session.exec(select(PushToken).where(PushToken.user_id == user.id)).all()
        dead = []
        for token in tokens:
            try:
                messaging.send(_build_message(token, title, body, link), app=app)
            except (messaging.UnregisteredError, messaging.SenderIdMismatchError):
                dead.append(token)
            except exceptions.InvalidArgumentError:
                dead.append(token)
            except Exception:
                logger.exception("FCM send failed for user %s", user.id)
        for token in dead:
            session.delete(token)
        if dead:
            session.commit()
    except Exception:
        logger.exception("send_push failed for user %s", user.id)
