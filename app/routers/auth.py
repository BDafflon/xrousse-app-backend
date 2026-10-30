import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db import get_session
from app.models.user import Role, User
from app.schemas.auth import LoginIn, RefreshIn, SignupIn, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def signup(data: SignupIn, session: Session = Depends(get_session)) -> TokenPair:
    existing = session.exec(select(User).where(User.email == data.email)).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        role=Role.lecteur,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return TokenPair(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
    )


@router.post("/login", response_model=TokenPair)
def login(data: LoginIn, session: Session = Depends(get_session)) -> TokenPair:
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
    )

    user = session.exec(select(User).where(User.email == data.email)).first()
    if user is None or not verify_password(data.password, user.password_hash):
        raise invalid_credentials

    return TokenPair(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshIn, session: Session = Depends(get_session)) -> TokenPair:
    invalid_token = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
    )

    try:
        payload = decode_token(data.refresh_token)
    except jwt.InvalidTokenError:
        raise invalid_token

    if payload.get("type") != "refresh":
        raise invalid_token

    user_id = payload.get("sub")
    if user_id is None:
        raise invalid_token

    user = session.get(User, int(user_id))
    if user is None:
        raise invalid_token

    return TokenPair(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout() -> dict:
    return {"detail": "Logged out"}
