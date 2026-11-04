from sqlmodel import Session, select

from app.models.event import Event
from app.models.event_share import EventShare
from app.models.saved_event import SavedEvent
from app.models.vote import Vote


def delete_event_cascade(event: Event, session: Session) -> None:
    """Delete an event along with the child rows that hold a FK to it
    (votes, saved events, shares). Neither has an ON DELETE rule nor an ORM cascade
    (see alembic/versions/0004 and 0010), so they must go first or Postgres
    raises an FK violation (500).
    """
    for model in (Vote, SavedEvent, EventShare):
        for row in session.exec(select(model).where(model.event_id == event.id)).all():
            session.delete(row)
    # No ORM relationship links these models to Event, so flush explicitly:
    # otherwise the unit-of-work may order the event DELETE first.
    session.flush()
    session.delete(event)
    session.commit()
