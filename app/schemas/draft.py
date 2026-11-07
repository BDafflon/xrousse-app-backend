from pydantic import BaseModel, Field, NaiveDatetime


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


class DraftPrixIn(BaseModel):
    # Single price = prix_min only; range = both; None/None clears the price.
    prix_min: float | None = Field(default=None, ge=0)
    prix_max: float | None = Field(default=None, ge=0)
