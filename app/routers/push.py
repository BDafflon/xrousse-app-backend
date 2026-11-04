from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth.dependencies import get_current_user
from app.db import get_session
from app.models.push_token import PushToken
from app.models.user import User

router = APIRouter(prefix="/me/push-tokens", tags=["push"])


class PushTokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=4096)
    platform: Literal["web", "android", "ios"]


@router.put("", status_code=status.HTTP_204_NO_CONTENT)
def register_token(
    data: PushTokenIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    """Register (or refresh) this device for push. Idempotent. If the token
    was registered by another account (shared device), it moves to the
    current user: a device only ever receives the pushes of whoever is
    logged in on it."""
    existing = session.exec(select(PushToken).where(PushToken.token == data.token)).first()
    if existing is None:
        session.add(
            PushToken(user_id=current_user.id, token=data.token, platform=data.platform)
        )
    else:
        existing.user_id = current_user.id
        existing.platform = data.platform
        session.add(existing)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/unregister", status_code=status.HTTP_204_NO_CONTENT)
def unregister_token(
    data: PushTokenIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    """Stop pushing to this device (logout / switch off). Idempotent; only
    removes the caller's own token."""
    token = session.exec(
        select(PushToken).where(
            PushToken.token == data.token, PushToken.user_id == current_user.id
        )
    ).first()
    if token is not None:
        session.delete(token)
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
