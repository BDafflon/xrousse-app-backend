import logging
from html import escape

from sqlmodel import Session, select

from app.config import get_settings
from app.models.event import Event
from app.models.notification import Notification, NotificationType
from app.models.user import Role, User
from app.services.email import send_email
from app.services.push import send_push

logger = logging.getLogger(__name__)


def notify(
    session: Session,
    user: User,
    type: NotificationType,
    title: str,
    message: str,
    *,
    event: Event | None = None,
    link: str | None = None,
) -> None:
    """Create an in-app notification for `user` and email them the same text,
    each channel only if the user hasn't turned it off in their preferences.

    Never raises: a notification failure (DB or Resend) must not break the
    request that triggered it. Call it AFTER the triggering change has been
    committed. All text is HTML-escaped in the email since titles, reasons
    etc. are user-provided.
    """
    if user.notify_in_app:
        try:
            session.add(
                Notification(
                    user_id=user.id,
                    type=type.value,
                    title=title,
                    message=message,
                    event_id=event.id if event is not None else None,
                    link=link,
                )
            )
            session.commit()
        except Exception:
            session.rollback()
            logger.exception(
                "Failed to store notification %s for user %s", type, user.id
            )

    if user.notify_in_app:
        # Push is the real-time delivery of the in-app notification, so it
        # follows the same switch (devices opt in by registering a token).
        send_push(session, user, title, message, link)

    if not user.notify_email:
        return
    try:
        settings = get_settings()
        html = f"<p><strong>{escape(title)}</strong></p><p>{escape(message)}</p>"
        if link:
            html += f'<p><a href="{escape(settings.site_url + link)}">Ouvrir</a></p>'
        send_email(user.email, title, html)
    except Exception:
        logger.exception("Failed to email notification %s to user %s", type, user.id)


def notify_admins(
    session: Session,
    type: NotificationType,
    title: str,
    message: str,
    *,
    event: Event | None = None,
    link: str | None = None,
    exclude_user_id: int | None = None,
) -> None:
    admins = session.exec(select(User).where(User.role == Role.admin)).all()
    for admin in admins:
        if admin.id != exclude_user_id:
            notify(session, admin, type, title, message, event=event, link=link)
