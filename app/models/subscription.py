from enum import Enum

from sqlmodel import Field, SQLModel, UniqueConstraint


class AlertMode(str, Enum):
    immediat = "immediat"
    resume = "resume"


class Subscription(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "tag_id", name="uq_subscription_user_tag"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    tag_id: int = Field(foreign_key="tag.id")
    mode: AlertMode = Field(default=AlertMode.immediat)
    resume_day: int | None = Field(default=None)
