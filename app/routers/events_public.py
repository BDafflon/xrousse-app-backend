import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.auth.dependencies import get_current_user_optional
from app.db import get_session
from app.models.event import Event, EventStatus, EventTag
from app.models.tag import Tag
from app.models.user import User
from app.models.vote import Vote
from app.schemas.event import EventCalendarOut, EventOut
from app.schemas.vote import VoteOut
from app.services.occurrences import next_occurrence, occurrences_in_range
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
    if event is None or event.statut != EventStatus.publie or event.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return event


@router.get("")
def list_events(
    view: Literal["mixed", "calendar", "permanent", "week"] = Query(default="mixed"),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None),
    tag: list[str] | None = Query(default=None),
    sort: str = Query(default="date"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    query = select(Event).where(
        Event.statut == EventStatus.publie, Event.is_deleted == False  # noqa: E712
    )

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
        # Widened window: an event's raw `date` alone is not enough to tell
        # whether it has an occurrence inside [start_of_month,
        # start_of_next_month) once multi-day ranges and recurrence are
        # involved. An event can never *start* on or after the end of this
        # month and still have an occurrence inside it, so `Event.date <
        # start_of_next_month` stays a hard upper bound in all cases. Beyond
        # that, which events whose `date` falls BEFORE the month can still
        # reach into it depends on the event's kind:
        #   - recurring (recurrence_jours set): its occurrences continue
        #     indefinitely unless `recurrence_fin` caps them, so it reaches
        #     into this month unless `recurrence_fin` already ended before
        #     the month started.
        #   - multi-day (date_fin set, no recurrence): it reaches into this
        #     month only if its range's end (`date_fin`) is on or after the
        #     start of the month.
        #   - plain single-day (neither set): it can only land in this month
        #     if its single `date` itself is on or after the start of the
        #     month (no range/recurrence to carry it forward).
        query = query.where(Event.date < start_of_next_month).where(
            or_(
                and_(
                    Event.recurrence_jours.is_not(None),
                    or_(
                        Event.recurrence_fin.is_(None),
                        Event.recurrence_fin >= start_of_month,
                    ),
                ),
                and_(Event.date_fin.is_not(None), Event.date_fin >= start_of_month),
                and_(
                    Event.date_fin.is_(None),
                    Event.recurrence_jours.is_(None),
                    Event.date >= start_of_month,
                ),
            )
        )
    elif view == "week":
        now = datetime.now(timezone.utc)
        # Same naive-bound requirement as the calendar view above: Event.date
        # is naive, so start_of_today must be naive too.
        start_of_today = datetime(now.year, now.month, now.day)
        query = (
            query.where(Event.is_permanent.is_(False))
            .where(Event.date < start_of_today + timedelta(days=7))
            .where(
                or_(
                    Event.date >= start_of_today,
                    and_(
                        Event.recurrence_jours.is_not(None),
                        or_(
                            Event.recurrence_fin.is_(None),
                            Event.recurrence_fin >= start_of_today,
                        ),
                    ),
                    and_(
                        Event.date_fin.is_not(None),
                        Event.date_fin >= start_of_today,
                    ),
                )
            )
        )

    if view == "mixed" and sort not in ("popularite", "nouveaute"):
        # Default "date" sort for the mixed view: a plain `Event.date.asc()`
        # sort would push every permanent event (date IS NULL) to one end of
        # the list (NULLS LAST on Postgres), burying them. Instead, fetch
        # dated and permanent events separately and interleave them: one
        # permanent event after every 5 dated events.
        dated_query = query.where(Event.is_permanent.is_(False)).order_by(
            Event.id.asc()
        )
        permanent_query = query.where(Event.is_permanent.is_(True)).order_by(
            Event.id.asc()
        )
        today = date.today()
        dated_events = sorted(
            session.exec(dated_query).all(),
            key=lambda event: next_occurrence(event, today) or date.max,
        )
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
        if sort == "popularite":
            query = query.order_by(Event.likes_count.desc())
        elif sort == "nouveaute":
            query = query.order_by(Event.id.desc())
        elif view != "week":
            # "week" and this default-date fallback are both sorted in Python
            # below, by next_occurrence rather than raw Event.date, since a
            # recurring event's next occurrence can differ from its stored
            # `date`. Order by id here for a deterministic fetch order prior
            # to that Python-side sort.
            query = query.order_by(Event.id.asc())

        if view == "mixed":
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)

        events = session.exec(query).all()

        if view == "week" and sort not in ("popularite", "nouveaute"):
            now = datetime.now(timezone.utc)
            start_of_today = date(now.year, now.month, now.day)
            events = sorted(
                events,
                key=lambda event: next_occurrence(event, start_of_today) or date.max,
            )
        elif view != "mixed" and sort not in ("popularite", "nouveaute"):
            # Same rationale as the "week" sort above: order by each event's
            # actual next occurrence rather than its raw stored `date`.
            today = date.today()
            events = sorted(
                events,
                key=lambda event: next_occurrence(event, today) or date.max,
            )

    if view == "calendar":
        # EventListOut.items is declared as list[EventOut]: dumping an
        # EventCalendarOut (a subclass with an extra `occurrences` field)
        # through that declared type — even via model_construct, which skips
        # validation but not pydantic's dump-by-declared-type behavior for
        # nested models — silently drops `occurrences`. So the calendar
        # branch bypasses EventListOut/response_model entirely and returns a
        # plain dict; having already dropped response_model from the route
        # decorator, FastAPI serializes each EventCalendarOut via its own
        # .model_dump(), keeping `occurrences`.
        calendar_items = [
            EventCalendarOut(
                **EventOut.model_validate(event, from_attributes=True).model_dump(),
                occurrences=occurrences_in_range(
                    event, start_of_month.date(), start_of_next_month.date()
                ),
            )
            for event in events
        ]
        return {"items": calendar_items, "page": page, "page_size": page_size}

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
