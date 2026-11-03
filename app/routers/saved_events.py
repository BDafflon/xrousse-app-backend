from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth.dependencies import get_current_user
from app.db import get_session
from app.models.event import Event, EventStatus
from app.models.saved_event import SavedEvent
from app.models.user import User
from app.schemas.event import EventOut
from app.services.occurrences import next_occurrence

router = APIRouter(prefix="/saved-events", tags=["saved-events"])


@router.get("", response_model=list[EventOut])
def list_saved_events(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Event]:
    """The current user's saved events (published only), soonest first;
    permanent events (no date) come last."""
    events = session.exec(
        select(Event)
        .join(SavedEvent, SavedEvent.event_id == Event.id)
        .where(SavedEvent.user_id == current_user.id)
        .where(Event.statut == EventStatus.publie)
    ).all()
    today = date.today()
    return sorted(
        events, key=lambda event: (next_occurrence(event, today) or date.max, event.id)
    )


@router.put("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def save_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    """Idempotent: saving an already-saved event is a no-op (204)."""
    event = session.get(Event, event_id)
    if event is None or event.statut != EventStatus.publie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    session.add(SavedEvent(user_id=current_user.id, event_id=event_id))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def unsave_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    """Idempotent: unsaving an event that isn't saved is a no-op (204)."""
    saved = session.exec(
        select(SavedEvent).where(
            SavedEvent.user_id == current_user.id, SavedEvent.event_id == event_id
        )
    ).first()
    if saved is not None:
        session.delete(saved)
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
