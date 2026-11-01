from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.auth.dependencies import get_current_user, require_role
from app.db import get_session
from app.models.event import Event, EventStatus
from app.models.user import Role, User
from app.schemas.draft import (
    DraftAppendDescriptionIn,
    DraftImageIn,
    DraftSourceIn,
    DraftTitleIn,
    DraftUpsertIn,
)
from app.schemas.event import EventOut

router = APIRouter(
    prefix="/drafts",
    tags=["drafts"],
    dependencies=[Depends(require_role(Role.admin, Role.redacteur))],
)


def _get_draft_or_404(draft_id: int, session: Session) -> Event:
    event = session.get(Event, draft_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found"
        )
    # Draft endpoints exist for the extension's draft-capture flow and are only
    # meant to touch events still in brouillon. A published event's titre/date
    # are validated at publish time and must not be nulled out or altered by a
    # draft endpoint called (accidentally or otherwise) on a published id.
    if event.statut != EventStatus.brouillon:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event is no longer a draft",
        )
    return event


@router.post("/upsert", response_model=EventOut)
def upsert_draft(
    data: DraftUpsertIn,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Event:
    existing = session.exec(
        select(Event).where(Event.source_url == data.source_url)
    ).first()
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return existing

    event = Event(
        source_url=data.source_url,
        titre=data.titre,
        description=data.description_append,
        statut=EventStatus.brouillon,
        created_by_id=current_user.id,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    response.status_code = status.HTTP_201_CREATED
    return event


@router.patch("/{draft_id}/title", response_model=EventOut)
def patch_draft_title(
    draft_id: int,
    data: DraftTitleIn,
    session: Session = Depends(get_session),
) -> Event:
    event = _get_draft_or_404(draft_id, session)
    event.titre = data.titre
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.patch("/{draft_id}/append-description", response_model=EventOut)
def append_draft_description(
    draft_id: int,
    data: DraftAppendDescriptionIn,
    session: Session = Depends(get_session),
) -> Event:
    event = _get_draft_or_404(draft_id, session)
    if event.description:
        event.description = f"{event.description}\n{data.text}"
    else:
        event.description = data.text
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.patch("/{draft_id}/source", response_model=EventOut)
def patch_draft_source(
    draft_id: int,
    data: DraftSourceIn,
    session: Session = Depends(get_session),
) -> Event:
    event = _get_draft_or_404(draft_id, session)

    conflicting = session.exec(
        select(Event).where(Event.source_url == data.source_url)
    ).first()
    if conflicting is not None and conflicting.id != event.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="source_url already in use by another event",
        )

    event.source_url = data.source_url
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.patch("/{draft_id}/image", response_model=EventOut)
def patch_draft_image(
    draft_id: int,
    data: DraftImageIn,
    session: Session = Depends(get_session),
) -> Event:
    event = _get_draft_or_404(draft_id, session)
    event.image_url = data.image_url
    session.add(event)
    session.commit()
    session.refresh(event)
    return event
