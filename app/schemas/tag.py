from pydantic import BaseModel


class TagIn(BaseModel):
    nom: str


class TagOut(BaseModel):
    id: int
    nom: str
    slug: str
    is_predefined: bool
