from sqlmodel import Field, SQLModel


class NewEventTagFilter(SQLModel, table=True):
    """Tags a user restricts their "new event" notifications to. No row for a
    user means "all tags"."""

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)
