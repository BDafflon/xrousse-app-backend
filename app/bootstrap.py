import logging

from sqlmodel import Session, select

from app.auth.security import hash_password
from app.config import get_settings
from app.models.user import Role, User

logger = logging.getLogger(__name__)


def bootstrap_admin(session: Session) -> None:
    """Create the first admin user from ADMIN_EMAIL/ADMIN_PASSWORD env vars.

    Opt-in and idempotent: does nothing unless both env vars are set, and does
    nothing if a user with that email already exists (safe to run on every
    startup/redeploy).
    """
    settings = get_settings()
    if not settings.admin_email or not settings.admin_password:
        return

    existing = session.exec(
        select(User).where(User.email == settings.admin_email)
    ).first()
    if existing is not None:
        return

    user = User(
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
        role=Role.admin,
    )
    session.add(user)
    session.commit()
    logger.info("Bootstrapped first admin user %s", settings.admin_email)
