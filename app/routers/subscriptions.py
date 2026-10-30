from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.dependencies import get_current_user, require_role
from app.db import get_session
from app.models.subscription import AlertMode, Subscription
from app.models.user import Role, User
from app.schemas.subscription import SubscriptionCreate, SubscriptionOut

router = APIRouter(
    prefix="/subscriptions",
    tags=["subscriptions"],
    dependencies=[Depends(require_role(Role.lecteur, Role.admin, Role.redacteur))],
)


@router.get("", response_model=list[SubscriptionOut])
def list_subscriptions(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Subscription]:
    subscriptions = session.exec(
        select(Subscription).where(Subscription.user_id == current_user.id)
    ).all()
    return list(subscriptions)


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_subscription(
    data: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Subscription:
    if data.mode == AlertMode.resume and data.resume_day is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="resume_day is required when mode is 'resume'",
        )

    existing = session.exec(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.tag_id == data.tag_id,
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subscription already exists for this tag",
        )

    subscription = Subscription(
        user_id=current_user.id,
        tag_id=data.tag_id,
        mode=data.mode,
        resume_day=data.resume_day,
    )
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return subscription


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    subscription = session.get(Subscription, subscription_id)
    if subscription is None or subscription.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )
    session.delete(subscription)
    session.commit()
