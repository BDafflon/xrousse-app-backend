from collections import defaultdict

from sqlmodel import Session, select

from app.config import get_settings
from app.models.event import Event, EventStatus
from app.models.subscription import AlertMode, Subscription
from app.models.user import User
from app.services.email import send_email


def trigger_immediate_alerts(event: Event, session: Session) -> None:
    """Send an immediate email to every user subscribed (mode=immediat) to
    any tag on `event`. Intended to be called synchronously right after an
    event is published (e.g. from the backoffice publish endpoint).
    """
    tag_ids = [tag.id for tag in event.tags]
    if not tag_ids:
        return

    subscriptions = session.exec(
        select(Subscription).where(
            Subscription.mode == AlertMode.immediat,
            Subscription.tag_id.in_(tag_ids),
        )
    ).all()
    if not subscriptions:
        return

    user_ids = {subscription.user_id for subscription in subscriptions}
    users = session.exec(select(User).where(User.id.in_(user_ids))).all()
    users_by_id = {user.id: user for user in users}

    settings = get_settings()
    subject = f"Nouvel événement : {event.titre}"
    for user_id in user_ids:
        user = users_by_id.get(user_id)
        if user is None:
            continue
        html = (
            f"<p>Un nouvel événement correspondant à vos abonnements vient d'être "
            f"publié : <strong>{event.titre}</strong>.</p>"
            f'<p><a href="{settings.site_url}/events/{event.id}">Voir l\'événement</a></p>'
        )
        send_email(user.email, subject, html)


def send_digest_for_day(day: int, session: Session) -> None:
    """Build and send one digest email per user for every `resume`
    subscription whose `resume_day` matches `day`. The digest lists
    published events matching the user's subscribed tags.

    Scheduling (cron) for calling this periodically is explicitly out of
    scope for this task; only the callable itself is provided.
    """
    subscriptions = session.exec(
        select(Subscription).where(
            Subscription.mode == AlertMode.resume,
            Subscription.resume_day == day,
        )
    ).all()
    if not subscriptions:
        return

    tag_ids_by_user: dict[int, set[int]] = defaultdict(set)
    for subscription in subscriptions:
        tag_ids_by_user[subscription.user_id].add(subscription.tag_id)

    settings = get_settings()

    for user_id, tag_ids in tag_ids_by_user.items():
        user = session.get(User, user_id)
        if user is None:
            continue

        events = session.exec(
            select(Event).where(Event.statut == EventStatus.publie)
        ).all()
        matching_events = [
            event
            for event in events
            if any(tag.id in tag_ids for tag in event.tags)
        ]
        if not matching_events:
            continue

        items = "".join(
            f'<li><a href="{settings.site_url}/events/{event.id}">{event.titre}</a></li>'
            for event in matching_events
        )
        html = f"<p>Voici les événements publiés cette semaine :</p><ul>{items}</ul>"
        send_email(user.email, "Votre résumé hebdomadaire", html)
