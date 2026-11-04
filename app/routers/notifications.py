from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.auth.dependencies import get_current_user
from app.db import get_session
from app.models.new_event_tag_filter import NewEventTagFilter
from app.models.notification import Notification
from app.models.tag import Tag
from app.models.user import User

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    message: str
    event_id: int | None
    link: str | None
    read: bool
    created_at: datetime


class PreferencesOut(BaseModel):
    notify_in_app: bool
    notify_email: bool
    notify_new_events: bool
    notify_event_shared: bool
    # Tags restricting the "new events" notifications; empty = all tags.
    new_event_tag_ids: list[int]


class PreferencesIn(BaseModel):
    """Every field is optional: only the ones sent are changed."""

    notify_in_app: bool | None = None
    notify_email: bool | None = None
    notify_new_events: bool | None = None
    notify_event_shared: bool | None = None
    new_event_tag_ids: list[int] | None = None


class UnreadCountOut(BaseModel):
    unread: int


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Notification]:
    query = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        query = query.where(Notification.read.is_(False))
    return list(
        session.exec(
            query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
        ).all()
    )


def _preferences_out(user: User, session: Session) -> PreferencesOut:
    tag_ids = session.exec(
        select(NewEventTagFilter.tag_id)
        .where(NewEventTagFilter.user_id == user.id)
        .order_by(NewEventTagFilter.tag_id)
    ).all()
    return PreferencesOut(
        notify_in_app=user.notify_in_app,
        notify_email=user.notify_email,
        notify_new_events=user.notify_new_events,
        notify_event_shared=user.notify_event_shared,
        new_event_tag_ids=list(tag_ids),
    )


@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PreferencesOut:
    return _preferences_out(current_user, session)


@router.put("/preferences", response_model=PreferencesOut)
def update_preferences(
    data: PreferencesIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PreferencesOut:
    for field in ("notify_in_app", "notify_email", "notify_new_events", "notify_event_shared"):
        value = getattr(data, field)
        if value is not None:
            setattr(current_user, field, value)
    session.add(current_user)

    if data.new_event_tag_ids is not None:
        valid = set(
            session.exec(select(Tag.id).where(Tag.id.in_(data.new_event_tag_ids))).all()
        )
        if valid != set(data.new_event_tag_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Tag inconnu",
            )
        for row in session.exec(
            select(NewEventTagFilter).where(NewEventTagFilter.user_id == current_user.id)
        ).all():
            session.delete(row)
        session.flush()
        for tag_id in valid:
            session.add(NewEventTagFilter(user_id=current_user.id, tag_id=tag_id))

    session.commit()
    session.refresh(current_user)
    return _preferences_out(current_user, session)


@router.get("/unread-count", response_model=UnreadCountOut)
def unread_count(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UnreadCountOut:
    count = session.exec(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id, Notification.read.is_(False))
    ).one()
    return UnreadCountOut(unread=count)


@router.post("/read-all", response_model=UnreadCountOut)
def read_all(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UnreadCountOut:
    for notification in session.exec(
        select(Notification).where(
            Notification.user_id == current_user.id, Notification.read.is_(False)
        )
    ).all():
        notification.read = True
        session.add(notification)
    session.commit()
    return UnreadCountOut(unread=0)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Notification:
    notification = session.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    notification.read = True
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification
