from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class PushToken(SQLModel, table=True):
    """A device/browser registered to receive push notifications (FCM token).
    One user can have several; a token belongs to exactly one user."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token: str = Field(unique=True, index=True)
    platform: str  # "web" | "android" | "ios"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
