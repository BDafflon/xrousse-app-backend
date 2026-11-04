from enum import Enum

from sqlmodel import Field, SQLModel


class TagFamily(str, Enum):
    enfant = "enfant"
    famille = "famille"
    culture = "culture"
    plein_air = "plein_air"
    solidarite = "solidarite"
    autre = "autre"


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    slug: str = Field(unique=True, index=True)
    is_predefined: bool = Field(default=False)
    famille: TagFamily = Field(default=TagFamily.autre)
    is_deleted: bool = Field(default=False)
