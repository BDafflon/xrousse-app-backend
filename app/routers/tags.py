from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.dependencies import require_role
from app.db import get_session
from app.models.tag import Tag
from app.models.user import Role
from app.schemas.tag import TagIn, TagOut
from app.seed_tags import slugify

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
def list_tags(
    include_deleted: bool = False, session: Session = Depends(get_session)
) -> list[Tag]:
    query = select(Tag)
    if not include_deleted:
        query = query.where(Tag.is_deleted == False)  # noqa: E712
    return list(session.exec(query).all())


@router.post(
    "",
    response_model=TagOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.admin, Role.redacteur))],
)
def create_tag(data: TagIn, session: Session = Depends(get_session)) -> Tag:
    slug = slugify(data.nom)
    existing = session.exec(select(Tag).where(Tag.slug == slug)).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Tag already exists"
        )

    tag = Tag(nom=data.nom, slug=slug, is_predefined=False, famille=data.famille)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.admin))],
)
def delete_tag(tag_id: int, session: Session = Depends(get_session)) -> None:
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    tag.is_deleted = True
    session.add(tag)
    session.commit()


@router.post(
    "/{tag_id}/restore",
    response_model=TagOut,
    dependencies=[Depends(require_role(Role.admin))],
)
def restore_tag(tag_id: int, session: Session = Depends(get_session)) -> Tag:
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    tag.is_deleted = False
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag
