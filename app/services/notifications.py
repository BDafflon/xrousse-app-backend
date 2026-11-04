import logging
from html import escape

from sqlmodel import Session, select

from app.config import get_settings
from app.models.event import Event
from app.models.new_event_tag_filter import NewEventTagFilter
from app.models.notification import Notification, NotificationType
from app.models.user import Role, User
from app.services.email import send_email
from app.services.push import send_push

logger = logging.getLogger(__name__)

# Notification types the recipient can switch off individually.
TYPE_PREFERENCE = {
    NotificationType.event_shared: "notify_event_shared",
    NotificationType.event_published: "notify_new_events",
}


def notify(
    session: Session,
    user: User,
    type: NotificationType,
    title: str,
    message: str,
    *,
    event: Event | None = None,
    link: str | None = None,
    send_mail: bool = True,
) -> None:
    """Create an in-app notification for `user` and email them the same text,
    each channel only if the user hasn't turned it off in their preferences,
    and nothing at all if they switched off this type of notification.
    `send_mail=False` skips the email (already sent by another path).

    Never raises: a notification failure (DB or Resend) must not break the
    request that triggered it. Call it AFTER the triggering change has been
    committed. All text is HTML-escaped in the email since titles, reasons
    etc. are user-provided.
    """
    preference = TYPE_PREFERENCE.get(type)
    if preference is not None and not getattr(user, preference):
        return

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

    if not send_mail or not user.notify_email:
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


def notify_new_event(
    session: Session, event: Event, *, already_emailed: set[int] | None = None
) -> None:
    """Tell opted-in users (notify_new_events) that `event` was published,
    honouring their optional tag filter (no filter = every tag). The author
    isn't notified. Users in `already_emailed` (tag-subscription email) get
    the in-app/push notification but not a second email.
    """
    already_emailed = already_emailed or set()
    event_tag_ids = {tag.id for tag in event.tags}
    users = session.exec(select(User).where(User.notify_new_events.is_(True))).all()
    if not users:
        return
    filters: dict[int, set[int]] = {}
    for row in session.exec(
        select(NewEventTagFilter).where(
            NewEventTagFilter.user_id.in_([u.id for u in users])
        )
    ).all():
        filters.setdefault(row.user_id, set()).add(row.tag_id)

    when = f" le {event.date:%d/%m/%Y}" if event.date else ""
    where = f" ({event.lieu})" if event.lieu else ""
    for user in users:
        if user.id == event.created_by_id:
            continue
        wanted = filters.get(user.id)
        if wanted and not (wanted & event_tag_ids):
            continue
        notify(
            session,
            user,
            NotificationType.event_published,
            f"Nouvel événement : {event.titre}",
            f"{event.titre}{when}{where}",
            event=event,
            link=f"/events/{event.id}",
            send_mail=user.id not in already_emailed,
        )
