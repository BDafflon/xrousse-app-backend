"""Pure occurrence resolver for multi-day and recurring events.

This module is intentionally independent of the API/schema layer: it consumes
only the raw `Event` model (app/models/event.py) and must never import from
`app/schemas/`. Callers (routers/services building calendar/week views) use
these functions to determine which calendar days an event occurs on and at
what times.
"""

from datetime import date, time, timedelta

from app.models.event import Event

# Safety bound for scanning ahead when looking for the next occurrence of a
# recurring event with no `recurrence_fin` set.
_MAX_LOOKAHEAD_DAYS = 370


def _parse_recurrence_jours(recurrence_jours: str) -> list[int]:
    """Parse a CSV-of-ISO-weekday-ints string (1=Monday..7=Sunday) into a list
    of ints. Duplicated locally (rather than imported from
    app/schemas/event.py) to keep this service free of schema-layer imports.
    Malformed/out-of-range input is treated as "no recurrence days" (empty
    list) since this module is not responsible for validating input — that is
    Task 2's job at the API boundary.
    """
    try:
        jours = [int(part) for part in recurrence_jours.split(",")]
    except ValueError:
        return []
    if any(jour < 1 or jour > 7 for jour in jours):
        return []
    return jours


def occurs_on(event: Event, day: date) -> tuple[time, time | None] | None:
    """Return (heure_debut, heure_fin_ou_None) if `event` occurs on `day`,
    else None. Permanent events always return None.
    """
    if event.is_permanent:
        return None
    if event.date is None:
        return None

    start_date = event.date.date()
    heure_debut = event.date.time()
    heure_fin = event.date_fin.time() if event.date_fin is not None else None

    if event.recurrence_jours:
        jours = _parse_recurrence_jours(event.recurrence_jours)
        if not jours:
            return None
        if day < start_date:
            return None
        if event.recurrence_fin is not None and day > event.recurrence_fin.date():
            return None
        if day.isoweekday() in jours:
            return (heure_debut, heure_fin)
        return None

    # Non-recurring: single day or multi-day inclusive range.
    end_date = event.date_fin.date() if event.date_fin is not None else start_date
    if start_date <= day <= end_date:
        return (heure_debut, heure_fin)
    return None


def occurrences_in_range(event: Event, start: date, end_exclusive: date) -> list[dict]:
    """For each day in [start, end_exclusive) where `occurs_on` is not None,
    return one dict {"date": "YYYY-MM-DD", "heure_debut": "HH:MM" | None,
    "heure_fin": "HH:MM" | None}.
    """
    results: list[dict] = []
    day = start
    while day < end_exclusive:
        occurrence = occurs_on(event, day)
        if occurrence is not None:
            heure_debut, heure_fin = occurrence
            results.append(
                {
                    "date": day.isoformat(),
                    "heure_debut": heure_debut.strftime("%H:%M") if heure_debut else None,
                    "heure_fin": heure_fin.strftime("%H:%M") if heure_fin else None,
                }
            )
        day += timedelta(days=1)
    return results


def next_occurrence(event: Event, on_or_after: date) -> date | None:
    """Return the first day >= on_or_after on which `occurs_on` is not None,
    searching at most 370 days ahead. None if none found.
    """
    day = on_or_after
    for _ in range(_MAX_LOOKAHEAD_DAYS):
        if occurs_on(event, day) is not None:
            return day
        day += timedelta(days=1)
    return None
