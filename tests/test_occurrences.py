from datetime import date, datetime

from app.models.event import Event, EventStatus
from app.services.occurrences import occurs_on, occurrences_in_range, next_occurrence


def _event(**kwargs):
    defaults = dict(
        source_url="https://example.com/x",
        created_by_id=1,
        statut=EventStatus.publie,
    )
    defaults.update(kwargs)
    return Event(**defaults)


def test_occurs_on_single_day_event_matches_only_that_day():
    event = _event(date=datetime(2026, 12, 5, 19, 0))
    assert occurs_on(event, date(2026, 12, 5)) == (datetime(2026, 12, 5, 19, 0).time(), None)
    assert occurs_on(event, date(2026, 12, 6)) is None


def test_occurs_on_multi_day_range_matches_every_day_inclusive():
    event = _event(
        date=datetime(2026, 12, 5, 10, 0),
        date_fin=datetime(2026, 12, 8, 18, 0),
    )
    assert occurs_on(event, date(2026, 12, 4)) is None
    assert occurs_on(event, date(2026, 12, 5)) is not None
    assert occurs_on(event, date(2026, 12, 6)) is not None
    assert occurs_on(event, date(2026, 12, 8)) is not None
    assert occurs_on(event, date(2026, 12, 9)) is None


def test_occurs_on_recurring_matches_chosen_weekdays_only():
    # 2026-11-03 is a Tuesday (isoweekday 2); recurrence_jours "2,5" = Tue+Fri
    event = _event(
        date=datetime(2026, 11, 3, 19, 0),
        date_fin=datetime(2026, 11, 3, 23, 0),
        recurrence_jours="2,5",
    )
    assert occurs_on(event, date(2026, 11, 3)) == (
        datetime(2026, 11, 3, 19, 0).time(),
        datetime(2026, 11, 3, 23, 0).time(),
    )
    assert occurs_on(event, date(2026, 11, 6)) == (
        datetime(2026, 11, 3, 19, 0).time(),
        datetime(2026, 11, 3, 23, 0).time(),
    )  # Friday same week
    assert occurs_on(event, date(2026, 11, 4)) is None  # Wednesday
    assert occurs_on(event, date(2026, 11, 2)) is None  # before start (Monday before)


def test_occurs_on_recurring_respects_recurrence_fin():
    event = _event(
        date=datetime(2026, 11, 3, 19, 0),
        recurrence_jours="2",
        recurrence_fin=datetime(2026, 11, 17, 0, 0),
    )
    assert occurs_on(event, date(2026, 11, 17)) is not None
    assert occurs_on(event, date(2026, 11, 24)) is None


def test_occurrences_in_range_returns_resolved_days_with_times():
    event = _event(
        date=datetime(2026, 12, 5, 10, 0),
        date_fin=datetime(2026, 12, 8, 18, 0),
    )
    result = occurrences_in_range(event, date(2026, 12, 1), date(2026, 12, 31))
    assert [item["date"] for item in result] == [
        "2026-12-05", "2026-12-06", "2026-12-07", "2026-12-08",
    ]
    assert result[0]["heure_debut"] == "10:00"
    assert result[0]["heure_fin"] == "18:00"


def test_occurrences_in_range_clips_to_window():
    event = _event(
        date=datetime(2026, 11, 29, 10, 0),
        date_fin=datetime(2026, 12, 3, 18, 0),
    )
    november = occurrences_in_range(event, date(2026, 11, 1), date(2026, 12, 1))
    assert [item["date"] for item in november] == ["2026-11-29", "2026-11-30"]


def test_next_occurrence_single_day():
    event = _event(date=datetime(2026, 12, 5, 19, 0))
    assert next_occurrence(event, date(2026, 12, 1)) == date(2026, 12, 5)
    assert next_occurrence(event, date(2026, 12, 6)) is None


def test_next_occurrence_recurring_finds_next_matching_weekday():
    event = _event(date=datetime(2026, 11, 3, 19, 0), recurrence_jours="2,5")
    assert next_occurrence(event, date(2026, 11, 4)) == date(2026, 11, 6)
