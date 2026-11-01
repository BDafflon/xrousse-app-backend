import hashlib
from datetime import datetime, timedelta, timezone
from typing import Literal

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
    view: Literal["mixed", "calendar", "permanent", "week"] = Query(default="mixed"),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None),
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

    if view == "permanent":
        query = query.where(Event.is_permanent.is_(True))
    elif view == "calendar":
        query = query.where(Event.is_permanent.is_(False))
        resolved_month = month
        resolved_year = year
        if resolved_month is None or resolved_year is None:
            now = datetime.now(timezone.utc)
            resolved_month = now.month
            resolved_year = now.year
        # Event.date is a naive column (local time as entered by the user,
        # never UTC — see Event.date's docstring). These bounds must stay
        # naive so Postgres compares them literally; a tz-aware bound would
        # make Postgres implicitly convert it to the session TimeZone before
        # comparing, silently shifting events across the month/day boundary
        # whenever that session timezone isn't UTC.
        start_of_month = datetime(resolved_year, resolved_month, 1)
        if resolved_month == 12:
            start_of_next_month = datetime(resolved_year + 1, 1, 1)
        else:
            start_of_next_month = datetime(resolved_year, resolved_month + 1, 1)
        query = query.where(Event.date >= start_of_month).where(
            Event.date < start_of_next_month
        )
    elif view == "week":
        now = datetime.now(timezone.utc)
        # Same naive-bound requirement as the calendar view above: Event.date
        # is naive, so start_of_today must be naive too.
        start_of_today = datetime(now.year, now.month, now.day)
        query = (
            query.where(Event.is_permanent.is_(False))
            .where(Event.date >= start_of_today)
            .where(Event.date < start_of_today + timedelta(days=7))
        )

    if view == "mixed" and sort not in ("popularite", "nouveaute"):
        # Default "date" sort for the mixed view: a plain `Event.date.asc()`
        # sort would push every permanent event (date IS NULL) to one end of
        # the list (NULLS LAST on Postgres), burying them. Instead, fetch
        # dated and permanent events separately and interleave them: one
        # permanent event after every 5 dated events.
        dated_query = query.where(Event.is_permanent.is_(False)).order_by(
            Event.date.asc()
        )
        permanent_query = query.where(Event.is_permanent.is_(True)).order_by(
            Event.id.asc()
        )
        dated_events = session.exec(dated_query).all()
        permanent_events = session.exec(permanent_query).all()

        merged: list[Event] = []
        dated_total = len(dated_events)
        permanent_total = len(permanent_events)
        permanent_index = 0
        for chunk_start in range(0, dated_total, 5):
            merged.extend(dated_events[chunk_start : chunk_start + 5])
            # Each permanent event may appear at most once in the merged
            # result. Once the permanent list is exhausted, stop inserting
            # (no `%` wraparound) — the remaining dated events then continue
            # uninterrupted with no more permanent insertions.
            if permanent_index < permanent_total:
                merged.append(permanent_events[permanent_index])
                permanent_index += 1
        # Dated events ran out before every permanent event had a turn in
        # the round-robin (e.g. zero or few dated events, or more permanents
        # than chunks): append whatever permanent events were never placed,
        # so none are dropped and none are repeated.
        if permanent_index < permanent_total:
            merged.extend(permanent_events[permanent_index:])

        offset = (page - 1) * page_size
        events = merged[offset : offset + page_size]
    else:
        if view == "week":
            query = query.order_by(Event.date.asc())
        elif sort == "popularite":
            query = query.order_by(Event.likes_count.desc())
        elif sort == "nouveaute":
            query = query.order_by(Event.id.desc())
        else:
            query = query.order_by(Event.date.asc())

        if view == "mixed":
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)

        events = session.exec(query).all()

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
