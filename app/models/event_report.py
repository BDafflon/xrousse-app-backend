from datetime import datetime, timezone

from sqlmodel import Field, SQLModel

REPORT_REASONS = ("hors_sujet", "inapproprie", "indesirable", "illegal", "spam")


class EventReport(SQLModel, table=True):
    """A member's report ("signaler") of a published event, handled by admins."""

    id: int | None = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    reporter_id: int = Field(foreign_key="user.id", index=True)
    reason: str
    # False while waiting for an admin; True once handled/dismissed.
    resolved: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
