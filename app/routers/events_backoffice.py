import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.auth.dependencies import get_current_user, require_role
from app.db import get_session
from app.models.event import Event, EventStatus, EventVisibility
from app.models.tag import Tag
from app.models.user import Role, User
from app.schemas.event import EventCreate, EventOut, EventUpdate, _validate_event_dates
from app.services.alerts import trigger_immediate_alerts
from app.services.events import delete_event_cascade

router = APIRouter(
    prefix="/backoffice/events",
    tags=["backoffice-events"],
    dependencies=[Depends(require_role(Role.admin, Role.redacteur))],
)


def _get_event_or_404(event_id: int, user: User, session: Session) -> Event:
    event = session.get(Event, event_id)
    # Users' private events are visible to admins only (moderation); for
    # redacteurs they don't exist (404, not 403).
    if event is None or (
        event.visibilite == EventVisibility.prive and user.role != Role.admin
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return event


def _resolve_tags(tag_ids: list[int], session: Session) -> list[Tag]:
    if not tag_ids:
        return []
    tags = session.exec(select(Tag).where(Tag.id.in_(tag_ids))).all()
    return list(tags)


@router.get("", response_model=list[EventOut])
def list_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Event]:
    offset = (page - 1) * page_size
    query = select(Event)
    if current_user.role != Role.admin:
        query = query.where(Event.visibilite == EventVisibility.public)
    events = session.exec(query.order_by(Event.id).offset(offset).limit(page_size)).all()
    return list(events)


@router.get("/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Event:
    return _get_event_or_404(event_id, current_user, session)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    data: EventCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Event:
    tags = _resolve_tags(data.tag_ids, session)
    event = Event(
        titre=data.titre,
        description=data.description,
        source_url=data.source_url,
        date=data.date,
        date_fin=data.date_fin,
        recurrence_jours=data.recurrence_jours,
        recurrence_fin=data.recurrence_fin,
        lieu=data.lieu,
        image_url=data.image_url,
        is_permanent=data.is_permanent,
        created_by_id=current_user.id,
        tags=tags,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.patch("/{event_id}", response_model=EventOut)
def update_event(
    event_id: int,
    data: EventUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Event:
    event = _get_event_or_404(event_id, current_user, session)
    update_data = data.model_dump(exclude_unset=True, exclude={"tag_ids"})
    for field, value in update_data.items():
        setattr(event, field, value)

    if data.tag_ids is not None:
        event.tags = _resolve_tags(data.tag_ids, session)

    # Re-validate against the MERGED event state (not just the raw PATCH
    # payload, which EventUpdate's own validator already checked in
    # isolation): a PATCH to a single field can still create an invalid
    # combination with the event's other already-stored fields, e.g.
    # `PATCH {"date": "..."}` pushing `date` past an already-stored
    # `date_fin`, or past an already-stored `recurrence_jours`.
    try:
        _validate_event_dates(
            event.date,
            event.date_fin,
            event.recurrence_jours,
            event.recurrence_fin,
            require_date=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))

    if event.statut == EventStatus.publie and (
        event.titre is None or (event.date is None and not event.is_permanent)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="titre et date requis pour un evenement publie",
        )

    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.post("/{event_id}/publish", response_model=EventOut)
def publish_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Event:
    event = _get_event_or_404(event_id, current_user, session)
    # User proposals go through /backoffice/moderation (admin only).
    if event.statut in (EventStatus.en_moderation, EventStatus.refuse) and (
        current_user.role != Role.admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul un admin peut moderer une proposition utilisateur",
        )
    if event.visibilite == EventVisibility.prive:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un event prive ne peut pas etre publie",
        )
    event.motif_refus = None
    if event.titre is None or (event.date is None and not event.is_permanent):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="titre et date requis pour publier",
        )
    event.statut = EventStatus.publie
    session.add(event)
    session.commit()
    session.refresh(event)

    try:
        trigger_immediate_alerts(event, session)
    except Exception:
        logging.getLogger(__name__).exception(
            "trigger_immediate_alerts failed for event %s", event.id
        )

    return event


@router.post("/{event_id}/feature", response_model=EventOut)
def feature_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Event:
    event = _get_event_or_404(event_id, current_user, session)
    event.featured_editorial = not event.featured_editorial
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.post("/{event_id}/unpublish", response_model=EventOut)
def unpublish_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Event:
    event = _get_event_or_404(event_id, current_user, session)
    event.statut = EventStatus.brouillon
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    event = _get_event_or_404(event_id, current_user, session)
    delete_event_cascade(event, session)
