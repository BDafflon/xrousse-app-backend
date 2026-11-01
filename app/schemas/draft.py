from pydantic import BaseModel, NaiveDatetime


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


class DraftImageIn(BaseModel):
    image_url: str


class DraftDateIn(BaseModel):
    date: NaiveDatetime | None = None


class DraftDateFinIn(BaseModel):
    date_fin: NaiveDatetime | None = None
