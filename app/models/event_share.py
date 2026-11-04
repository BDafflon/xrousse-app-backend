from datetime import datetime, timezone

from sqlmodel import Field, SQLModel, UniqueConstraint


class EventShare(SQLModel, table=True):
    """Read-only access to a private event granted by its owner to another
    member (`user_id` is the recipient)."""

    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_event_share_user_event"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
