from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, select

from app.db import get_session
from app.models.event import Event, EventStatus
from app.services.rss import build_feed

router = APIRouter(tags=["rss"])


@router.get("/rss.xml")
def rss_feed(session: Session = Depends(get_session)) -> Response:
    events = session.exec(
        select(Event)
        .where(Event.statut == EventStatus.publie)
        .order_by(Event.date.desc())
    ).all()
    return Response(content=build_feed(list(events)), media_type="application/rss+xml")
