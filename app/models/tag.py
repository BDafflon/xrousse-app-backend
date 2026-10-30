from sqlmodel import Field, SQLModel


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    slug: str = Field(unique=True, index=True)
    is_predefined: bool = Field(default=False)
