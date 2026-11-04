from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ReportReason = Literal["hors_sujet", "inapproprie", "indesirable", "illegal", "spam"]


class ReportIn(BaseModel):
    reason: ReportReason


class ReportOut(BaseModel):
    id: int
    event_id: int
    event_titre: str | None
    reporter_email: str
    reason: str
    resolved: bool
    created_at: datetime
