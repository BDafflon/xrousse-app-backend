import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_password_reset_token,
)
from app.config import get_settings
from app.db import get_session
from app.models.user import Role, User
from app.schemas.auth import (
    ForgotPasswordIn,
    LoginIn,
    RefreshIn,
    ResetPasswordIn,
    SignupIn,
    TokenPair,
)
from app.services.email import send_email

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


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(data: ForgotPasswordIn, session: Session = Depends(get_session)) -> dict:
    # Always return the same response whether or not the email exists, so
    # this endpoint can't be used to enumerate registered accounts.
    user = session.exec(select(User).where(User.email == data.email)).first()
    if user is not None:
        token = create_password_reset_token(user)
        settings = get_settings()
        reset_link = f"{settings.site_url}/reset-password?token={token}"
        send_email(
            to=user.email,
            subject="Réinitialisation de votre mot de passe",
            html=(
                f"<p>Vous avez demandé à réinitialiser votre mot de passe sur "
                f"Reco Croix-Rousse.</p>"
                f'<p><a href="{reset_link}">Cliquez ici pour choisir un nouveau mot de passe</a></p>'
                f"<p>Ce lien expire dans 1 heure. Si vous n'êtes pas à l'origine de "
                f"cette demande, vous pouvez ignorer cet e-mail.</p>"
            ),
        )
    return {"detail": "If that email is registered, a reset link has been sent"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(data: ResetPasswordIn, session: Session = Depends(get_session)) -> dict:
    invalid_token = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link"
    )
    try:
        payload = decode_token(data.token)
    except jwt.InvalidTokenError:
        raise invalid_token

    if payload.get("type") != "password_reset":
        raise invalid_token

    user_id = payload.get("sub")
    if user_id is None:
        raise invalid_token

    user = session.get(User, int(user_id))
    if user is None or not verify_password_reset_token(data.token, user):
        raise invalid_token

    user.password_hash = hash_password(data.new_password)
    session.add(user)
    session.commit()
    return {"detail": "Password updated"}
