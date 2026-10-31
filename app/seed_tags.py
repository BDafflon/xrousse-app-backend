import re

from sqlmodel import Session, select

from app.models.tag import Tag, TagFamily

PREDEFINED_TAGS: list[tuple[str, TagFamily]] = [
    ("Concert", TagFamily.culture),
    ("Marché", TagFamily.plein_air),
    ("Atelier", TagFamily.enfant),
    ("Exposition", TagFamily.culture),
    ("Sport", TagFamily.plein_air),
    ("Enfants", TagFamily.enfant),
    ("Solidarité", TagFamily.solidarite),
]


def slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def seed(session: Session) -> None:
    for nom, famille in PREDEFINED_TAGS:
        slug = slugify(nom)
        existing = session.exec(select(Tag).where(Tag.slug == slug)).first()
        if existing is not None:
            continue
        session.add(Tag(nom=nom, slug=slug, is_predefined=True, famille=famille))
    session.commit()
