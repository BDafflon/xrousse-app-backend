import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import format_datetime
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models.event import Event

_LOCAL_TZ = ZoneInfo("Europe/Paris")
_FEED_TITLE = "Reco Croix-Rousse"
_FEED_DESCRIPTION = "Événements recommandés dans le quartier de la Croix-Rousse"


def _to_rfc822(value: datetime) -> str:
    # Event dates are naive local (Lyon) times; attach the local zone before converting to UTC.
    aware = value.replace(tzinfo=_LOCAL_TZ).astimezone(ZoneInfo("UTC"))
    return format_datetime(aware)


def build_feed(events: list[Event], site_url: str | None = None) -> str:
    if site_url is None:
        site_url = get_settings().site_url
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = _FEED_TITLE
    ET.SubElement(channel, "link").text = site_url
    ET.SubElement(channel, "description").text = _FEED_DESCRIPTION

    for event in events:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = event.titre or ""
        ET.SubElement(item, "description").text = event.description or ""
        ET.SubElement(item, "link").text = event.source_url
        if event.date is not None:
            ET.SubElement(item, "pubDate").text = _to_rfc822(event.date)

    body = ET.tostring(rss, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{body}'
