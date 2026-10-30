from pydantic import BaseModel


class DraftUpsertIn(BaseModel):
    source_url: str
    titre: str | None = None
    description_append: str | None = None


class DraftTitleIn(BaseModel):
    titre: str | None = None


class DraftAppendDescriptionIn(BaseModel):
    text: str


class DraftSourceIn(BaseModel):
    source_url: str
