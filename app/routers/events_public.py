import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.auth.dependencies import get_current_user_optional
from app.db import get_session
from app.models.event import Event, EventStatus, EventTag
from app.models.tag import Tag
from app.models.user import User
from app.models.vote import Vote
from app.schemas.event import EventOut
from app.schemas.vote import VoteOut
from app.services.votes import get_or_create_anon_id

router = APIRouter(prefix="/events", tags=["events"])

# Basic anti-spam cap: a cookieless vote loop with no cookie sent gets a
# fresh anonymous identity on every request, so likes_count could otherwise
# be inflated without limit. This caps votes per (event, IP) within a
# rolling window, independent of anon_id/user_id dedup.
_VOTE_RATE_LIMIT_MAX = 5
_VOTE_RATE_LIMIT_WINDOW = timedelta(days=1)


def _hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode()).hexdigest()


class EventListOut(BaseModel):
    items: list[EventOut]
    page: int
    page_size: int


def _get_published_event_or_404(event_id: int, session: Session) -> Event:
    event = session.get(Event, event_id)
    if event is None or event.statut != EventStatus.publie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return event


@router.get("", response_model=EventListOut)
def list_events(
    tag: list[str] | None = Query(default=None),
    sort: str = Query(default="date"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> EventListOut:
    query = select(Event).where(Event.statut == EventStatus.publie)

    if tag:
        query = (
            query.join(EventTag, EventTag.event_id == Event.id)
            .join(Tag, Tag.id == EventTag.tag_id)
            .where(Tag.slug.in_(tag))
            .distinct()
        )

    if sort == "popularite":
        query = query.order_by(Event.likes_count.desc())
    elif sort == "nouveaute":
        query = query.order_by(Event.id.desc())
    else:
        query = query.order_by(Event.date.asc())

    offset = (page - 1) * page_size
    events = session.exec(query.offset(offset).limit(page_size)).all()

    items = [EventOut.model_validate(event, from_attributes=True) for event in events]
    return EventListOut(items=items, page=page, page_size=page_size)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, session: Session = Depends(get_session)) -> Event:
    return _get_published_event_or_404(event_id, session)


@router.post("/{event_id}/vote", response_model=VoteOut)
def vote_event(
    event_id: int,
    request: Request,
    response: Response,
    current_user: User | None = Depends(get_current_user_optional),
    session: Session = Depends(get_session),
) -> VoteOut:
    event = _get_published_event_or_404(event_id, session)

    client_ip = request.client.host if request.client else None
    ip_hash = _hash_ip(client_ip)

    if ip_hash is not None:
        window_start = datetime.now(timezone.utc) - _VOTE_RATE_LIMIT_WINDOW
        recent_votes = session.exec(
            select(func.count()).where(
                Vote.event_id == event.id,
                Vote.ip_hash == ip_hash,
                Vote.created_at >= window_start,
            )
        ).one()
        if recent_votes >= _VOTE_RATE_LIMIT_MAX:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many votes from this network for this event",
            )

    if current_user is not None:
        vote = Vote(event_id=event.id, user_id=current_user.id, ip_hash=ip_hash)
    else:
        anon_id = get_or_create_anon_id(request, response)
        vote = Vote(event_id=event.id, anon_id=anon_id, ip_hash=ip_hash)

    session.add(vote)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already voted for this event",
        )

    event.likes_count += 1
    session.add(event)
    session.commit()
    session.refresh(event)

    return VoteOut(likes_count=event.likes_count)
