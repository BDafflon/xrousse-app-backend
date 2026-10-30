from pydantic import BaseModel


class VoteOut(BaseModel):
    likes_count: int
