from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class Role(str, Enum):
    admin = "admin"
    redacteur = "redacteur"
    lecteur = "lecteur"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    role: Role = Field(default=Role.lecteur)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
