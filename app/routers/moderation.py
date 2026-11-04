import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.auth.dependencies import require_role
from app.db import get_session
from app.models.event import Event, EventStatus, EventVisibility
from app.models.user import Role, User
from app.schemas.event import ModerationEventOut, RejectIn
from app.models.notification import NotificationType
from app.services.alerts import trigger_immediate_alerts
from app.services.notifications import notify, notify_new_event

router = APIRouter(
    prefix="/backoffice/moderation",
    tags=["backoffice-moderation"],
    dependencies=[Depends(require_role(Role.admin))],
)


def _to_out(event: Event, session: Session) -> ModerationEventOut:
    author = session.get(User, event.created_by_id)
    return ModerationEventOut.model_validate(
        {
            **event.model_dump(),
            "tags": event.tags,
            "created_by_email": author.email if author else "",
        }
    )


def _get_pending_or_404(event_id: int, session: Session) -> Event:
    event = session.get(Event, event_id)
    if (
        event is None
        or event.visibilite != EventVisibility.public
        or event.statut != EventStatus.en_moderation
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune proposition en attente avec cet id",
        )
    return event


@router.get("/events", response_model=list[ModerationEventOut])
def list_pending(
    statut: EventStatus = Query(default=EventStatus.en_moderation),
    session: Session = Depends(get_session),
) -> list[ModerationEventOut]:
    """Moderation queue, oldest first. `statut=refuse` lists past rejections."""
    if statut not in (EventStatus.en_moderation, EventStatus.refuse):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="statut doit etre en_moderation ou refuse",
        )
    events = session.exec(
        select(Event)
        .where(Event.visibilite == EventVisibility.public, Event.statut == statut)
        .order_by(Event.id)
    ).all()
    return [_to_out(event, session) for event in events]


@router.post("/events/{event_id}/approve", response_model=ModerationEventOut)
def approve(event_id: int, session: Session = Depends(get_session)):
    event = _get_pending_or_404(event_id, session)
    event.statut = EventStatus.publie
    event.motif_refus = None
    session.add(event)
    session.commit()
    session.refresh(event)

    emailed: set[int] = set()
    try:
        emailed = trigger_immediate_alerts(event, session) or set()
    except Exception:
        logging.getLogger(__name__).exception(
            "trigger_immediate_alerts failed for event %s", event.id
        )
    try:
        notify_new_event(session, event, already_emailed=emailed)
    except Exception:
        logging.getLogger(__name__).exception(
            "notify_new_event failed for event %s", event.id
        )
    author = session.get(User, event.created_by_id)
    if author is not None:
        notify(
            session,
            author,
            NotificationType.proposal_approved,
            "Votre événement a été publié",
            f"« {event.titre} » a été validé par la modération.",
            event=event,
            link=f"/events/{event.id}",
        )
    return _to_out(event, session)


@router.post("/events/{event_id}/reject", response_model=ModerationEventOut)
def reject(event_id: int, data: RejectIn, session: Session = Depends(get_session)):
    motif = data.motif.strip()
    if not motif:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Un motif de refus est requis",
        )
    event = _get_pending_or_404(event_id, session)
    event.statut = EventStatus.refuse
    event.motif_refus = motif
    session.add(event)
    session.commit()
    session.refresh(event)
    author = session.get(User, event.created_by_id)
    if author is not None:
        notify(
            session,
            author,
            NotificationType.proposal_rejected,
            "Votre événement a été refusé",
            f"« {event.titre} » n'a pas été retenu. Motif : {motif}",
            event=event,
            link="/my-events/created",
        )
    return _to_out(event, session)
