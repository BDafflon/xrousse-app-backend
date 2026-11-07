import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.auth.dependencies import get_current_user
from app.db import get_session
from app.models.event import Event, EventStatus, EventVisibility
from app.models.event_share import EventShare
from app.models.tag import Tag
from app.models.user import User
from app.schemas.event import (
    EventOut,
    ShareIn,
    ShareOut,
    UserEventCreate,
    UserEventUpdate,
    _validate_event_dates,
    _validate_event_prix,
)
from app.models.notification import NotificationType
from app.services.events import delete_event_cascade
from app.services.notifications import notify, notify_admins

router = APIRouter(prefix="/me/events", tags=["me-events"])

# Anti-spam: max public proposals a single user can have waiting for
# moderation at the same time.
MAX_PENDING_PROPOSALS = 10


def _get_own_event_or_404(event_id: int, user: User, session: Session) -> Event:
    event = session.get(Event, event_id)
    # 404 (not 403) for someone else's event, so ids can't be probed.
    if event is None or event.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return event


def _resolve_tags(tag_ids: list[int], session: Session) -> list[Tag]:
    if not tag_ids:
        return []
    return list(session.exec(select(Tag).where(Tag.id.in_(tag_ids))).all())


def _notify_submission(event: Event, author: User, session: Session) -> None:
    notify_admins(
        session,
        NotificationType.proposal_submitted,
        "Nouvelle proposition à modérer",
        f"{author.email} propose « {event.titre} ».",
        event=event,
        link="/admin/moderation",
        exclude_user_id=author.id,
    )


def _require_submittable(event: Event) -> None:
    if event.titre is None or (event.date is None and not event.is_permanent):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="titre et date requis pour proposer un evenement public",
        )


def _apply_workflow_status(event: Event, user: User, session: Session) -> None:
    """Derive `statut` from `visibilite`: private events stay drafts forever,
    public ones (re)enter the moderation queue. Any edit of a public event
    therefore requires a new admin approval, so approved content can't be
    swapped for something else afterwards.
    """
    if event.visibilite == EventVisibility.prive:
        event.statut = EventStatus.brouillon
        event.motif_refus = None
        return

    _require_submittable(event)
    # A public event no longer needs (nor should keep) private shares: going
    # back to private later must be an explicit re-share.
    if event.id is not None:
        for share in session.exec(
            select(EventShare).where(EventShare.event_id == event.id)
        ).all():
            session.delete(share)
    if event.statut != EventStatus.en_moderation:
        pending = session.exec(
            select(func.count())
            .select_from(Event)
            .where(
                Event.created_by_id == user.id,
                Event.statut == EventStatus.en_moderation,
            )
        ).one()
        if pending >= MAX_PENDING_PROPOSALS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de propositions en attente de moderation",
            )
    event.statut = EventStatus.en_moderation
    event.motif_refus = None
    # Featuring is an editorial decision, never carried over from an edit.
    event.featured_editorial = False


@router.get("", response_model=list[EventOut])
def list_my_events(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Event]:
    return list(
        session.exec(
            select(Event)
            .where(Event.created_by_id == current_user.id)
            .order_by(Event.id.desc())
        ).all()
    )


@router.get("/shared-with-me", response_model=list[EventOut])
def list_shared_with_me(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Event]:
    """Private events other members shared with the current user (read-only)."""
    return list(
        session.exec(
            select(Event)
            .join(EventShare, EventShare.event_id == Event.id)
            .where(
                EventShare.user_id == current_user.id,
                Event.visibilite == EventVisibility.prive,
            )
            .order_by(Event.id.desc())
        ).all()
    )


@router.get("/{event_id}", response_model=EventOut)
def get_my_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Event:
    """Own event, or a private event shared with the current user."""
    event = session.get(Event, event_id)
    if event is not None and event.created_by_id != current_user.id:
        shared = session.exec(
            select(EventShare).where(
                EventShare.event_id == event_id,
                EventShare.user_id == current_user.id,
            )
        ).first()
        if shared is None or event.visibilite != EventVisibility.prive:
            event = None
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return event


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_my_event(
    data: UserEventCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Event:
    event = Event(
        titre=data.titre,
        description=data.description,
        # source_url is NOT NULL + unique: private memos / proposals without a
        # source get a unique placeholder.
        source_url=data.source_url or f"user-event:{uuid.uuid4()}",
        date=data.date,
        date_fin=data.date_fin,
        recurrence_jours=data.recurrence_jours,
        recurrence_fin=data.recurrence_fin,
        lieu=data.lieu,
        prix_min=data.prix_min,
        prix_max=data.prix_max,
        image_url=data.image_url,
        is_permanent=data.is_permanent,
        visibilite=data.visibilite,
        created_by_id=current_user.id,
        tags=_resolve_tags(data.tag_ids, session),
    )
    _apply_workflow_status(event, current_user, session)
    session.add(event)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="source_url deja utilisee"
        )
    session.refresh(event)
    if event.statut == EventStatus.en_moderation:
        _notify_submission(event, current_user, session)
    return event


@router.patch("/{event_id}", response_model=EventOut)
def update_my_event(
    event_id: int,
    data: UserEventUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Event:
    event = _get_own_event_or_404(event_id, current_user, session)
    previous_statut = event.statut
    update_data = data.model_dump(exclude_unset=True, exclude={"tag_ids"})
    for field, value in update_data.items():
        setattr(event, field, value)
    if data.tag_ids is not None:
        event.tags = _resolve_tags(data.tag_ids, session)

    try:
        _validate_event_prix(event.prix_min, event.prix_max)
        _validate_event_dates(
            event.date,
            event.date_fin,
            event.recurrence_jours,
            event.recurrence_fin,
            require_date=True,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )
    if event.titre is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="titre requis"
        )

    _apply_workflow_status(event, current_user, session)
    session.add(event)
    session.commit()
    session.refresh(event)
    if (
        event.statut == EventStatus.en_moderation
        and previous_statut != EventStatus.en_moderation
    ):
        _notify_submission(event, current_user, session)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    event = _get_own_event_or_404(event_id, current_user, session)
    delete_event_cascade(event, session)


def _share_out(user: User) -> ShareOut:
    return ShareOut(user_id=user.id, email=user.email)


@router.get("/{event_id}/shares", response_model=list[ShareOut])
def list_shares(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ShareOut]:
    _get_own_event_or_404(event_id, current_user, session)
    users = session.exec(
        select(User)
        .join(EventShare, EventShare.user_id == User.id)
        .where(EventShare.event_id == event_id)
        .order_by(User.email)
    ).all()
    return [_share_out(u) for u in users]


@router.post(
    "/{event_id}/shares", response_model=ShareOut, status_code=status.HTTP_201_CREATED
)
def share_event(
    event_id: int,
    data: ShareIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ShareOut:
    """Share a private event (read-only) with another member, by email.
    Idempotent: re-sharing with the same member is a no-op."""
    event = _get_own_event_or_404(event_id, current_user, session)
    if event.visibilite != EventVisibility.prive:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seuls les events prives peuvent etre partages",
        )
    recipient = session.exec(
        select(User).where(func.lower(User.email) == data.email.strip().lower())
    ).first()
    if recipient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Membre introuvable"
        )
    if recipient.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Impossible de partager avec soi-meme",
        )
    session.add(EventShare(user_id=recipient.id, event_id=event_id))
    newly_shared = True
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        newly_shared = False
    if newly_shared:
        notify(
            session,
            recipient,
            NotificationType.event_shared,
            "Un événement a été partagé avec vous",
            f"{current_user.email} a partagé « {event.titre} » avec vous.",
            event=event,
            link="/my-events/created",
        )
    return _share_out(recipient)


@router.delete(
    "/{event_id}/shares/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_share(
    event_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    """The owner revokes a share, or the recipient leaves a shared event."""
    event = session.get(Event, event_id)
    if event is None or (
        event.created_by_id != current_user.id and user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    share = session.exec(
        select(EventShare).where(
            EventShare.event_id == event_id, EventShare.user_id == user_id
        )
    ).first()
    if share is not None:
        session.delete(share)
        session.commit()
