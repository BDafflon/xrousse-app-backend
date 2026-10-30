from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.dependencies import require_role
from app.auth.security import hash_password
from app.db import get_session
from app.models.user import Role, User
from app.schemas.user import UserCreateByAdmin, UserOut

router = APIRouter(
    prefix="/backoffice/users",
    tags=["backoffice-users"],
    dependencies=[Depends(require_role(Role.admin))],
)


def _get_user_or_404(user_id: int, session: Session) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.get("", response_model=list[UserOut])
def list_users(session: Session = Depends(get_session)) -> list[User]:
    users = session.exec(select(User)).all()
    return list(users)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreateByAdmin, session: Session = Depends(get_session)
) -> User:
    existing = session.exec(select(User).where(User.email == data.email)).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, session: Session = Depends(get_session)) -> None:
    user = _get_user_or_404(user_id, session)

    if user.role == Role.admin:
        admin_count = len(
            session.exec(select(User).where(User.role == Role.admin)).all()
        )
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last remaining admin",
            )

    session.delete(user)
    session.commit()
