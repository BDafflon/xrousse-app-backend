from pydantic import BaseModel

from app.models.subscription import AlertMode


class SubscriptionCreate(BaseModel):
    tag_id: int
    mode: AlertMode
    resume_day: int | None = None


class SubscriptionOut(BaseModel):
    id: int
    user_id: int
    tag_id: int
    mode: AlertMode
    resume_day: int | None
