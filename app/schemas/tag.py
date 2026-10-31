from pydantic import BaseModel

from app.models.tag import TagFamily


class TagIn(BaseModel):
    nom: str
    famille: TagFamily = TagFamily.autre


class TagOut(BaseModel):
    id: int
    nom: str
    slug: str
    is_predefined: bool
    famille: TagFamily
