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
def list_tags(session: Session = Depends(get_session)) -> list[Tag]:
    return list(session.exec(select(Tag)).all())


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
