from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class NotificationType(str, Enum):
    proposal_submitted = "proposal_submitted"  # to admins
    proposal_approved = "proposal_approved"  # to the author
    proposal_rejected = "proposal_rejected"  # to the author
    event_shared = "event_shared"  # to the recipient
    event_published = "event_published"  # new public event, to opted-in users


class Notification(SQLModel, table=True):
    """In-app notification (the "pastille" counts the unread ones). The same
    event also goes out by email, see app/services/notifications.py."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # Stored as a plain string (validated by NotificationType in code) so new
    # types never require an enum migration on Postgres.
    type: str
    title: str
    message: str
    event_id: int | None = Field(default=None, foreign_key="event.id", index=True)
    # Frontend path to open when the notification is clicked.
    link: str | None = Field(default=None)
    read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
