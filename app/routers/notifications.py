from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.auth.dependencies import get_current_user
from app.db import get_session
from app.models.notification import Notification
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


@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.put("/preferences", response_model=PreferencesOut)
def update_preferences(
    data: PreferencesOut,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> User:
    current_user.notify_in_app = data.notify_in_app
    current_user.notify_email = data.notify_email
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


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
