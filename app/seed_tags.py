import re

from sqlmodel import Session, select

from app.models.tag import Tag

PREDEFINED_TAGS: list[str] = [
    "Concert",
    "Marché",
    "Atelier",
    "Exposition",
    "Sport",
    "Enfants",
    "Solidarité",
]


def slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def seed(session: Session) -> None:
    for nom in PREDEFINED_TAGS:
        slug = slugify(nom)
        existing = session.exec(select(Tag).where(Tag.slug == slug)).first()
        if existing is not None:
            continue
        session.add(Tag(nom=nom, slug=slug, is_predefined=True))
    session.commit()
