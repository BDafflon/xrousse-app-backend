from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import Role


class UserOut(BaseModel):
    id: int
    email: str
    role: Role
    created_at: datetime


class UserCreateByAdmin(BaseModel):
    email: EmailStr
    password: str
    role: Role
