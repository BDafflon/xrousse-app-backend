def test_list_only_returns_published(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    client.post(
        "/backoffice/events", json={"source_url": "https://example.com/f1"}, headers=headers
    )
    response = client.get("/events")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_vote_increments_likes_count(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/f2",
            "titre": "Fete",
            "date": "2026-11-20T10:00:00",
        },
        headers=headers,
    )
    event_id = created.json()["id"]
    client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    response = client.post(f"/events/{event_id}/vote")
    assert response.status_code == 200
    assert response.json()["likes_count"] == 1


def test_duplicate_anonymous_vote_rejected(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/f3",
            "titre": "Fete2",
            "date": "2026-11-21T10:00:00",
        },
        headers=headers,
    )
    event_id = created.json()["id"]
    client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    first = client.post(f"/events/{event_id}/vote")
    second = client.post(f"/events/{event_id}/vote")
    assert second.status_code == 409


def test_vote_as_authenticated_lecteur_dedups_on_user(client, redacteur_token, lecteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/f4",
            "titre": "Fete3",
            "date": "2026-11-22T10:00:00",
        },
        headers=headers,
    )
    event_id = created.json()["id"]
    client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    lecteur_headers = {"Authorization": f"Bearer {lecteur_token}"}
    first = client.post(f"/events/{event_id}/vote", headers=lecteur_headers)
    second = client.post(f"/events/{event_id}/vote", headers=lecteur_headers)
    assert first.status_code == 200
    assert second.status_code == 409


def test_get_event_detail_404_if_not_published(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events", json={"source_url": "https://example.com/f5"}, headers=headers
    )
    event_id = created.json()["id"]
    response = client.get(f"/events/{event_id}")
    assert response.status_code == 404


def test_get_event_detail_404_if_missing(client):
    response = client.get("/events/999999")
    assert response.status_code == 404


def test_get_event_detail_returns_published(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/f6",
            "titre": "Fete4",
            "date": "2026-11-23T10:00:00",
        },
        headers=headers,
    )
    event_id = created.json()["id"]
    client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    response = client.get(f"/events/{event_id}")
    assert response.status_code == 200
    assert response.json()["id"] == event_id


def test_list_filter_by_tag_and_sort_popularite(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created_a = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/f7",
            "titre": "A",
            "date": "2026-11-24T10:00:00",
        },
        headers=headers,
    )
    created_b = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/f8",
            "titre": "B",
            "date": "2026-11-25T10:00:00",
        },
        headers=headers,
    )
    id_a = created_a.json()["id"]
    id_b = created_b.json()["id"]
    client.post(f"/backoffice/events/{id_a}/publish", headers=headers)
    client.post(f"/backoffice/events/{id_b}/publish", headers=headers)

    # vote twice on b (two different anon identities via separate clients), once on a
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as other_client:
        other_client.post(f"/events/{id_b}/vote")
    client.post(f"/events/{id_b}/vote")
    client.post(f"/events/{id_a}/vote")

    response = client.get("/events", params={"sort": "popularite"})
    assert response.status_code == 200
    items = response.json()["items"]
    ids_in_order = [item["id"] for item in items]
    assert ids_in_order.index(id_b) < ids_in_order.index(id_a)


def test_cookieless_vote_loop_past_cap_is_rejected(client, redacteur_token):
    # Regression for I4: without a cookie, each POST gets a fresh anonymous
    # identity, so dedup-by-anon_id alone doesn't stop a vote loop. The
    # per-IP-per-event rate cap must kick in instead (TestClient reports the
    # same 'testclient' host for every request, so no special setup needed
    # to simulate "same IP").
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/ratecap1",
            "titre": "Fete rate cap",
            "date": "2026-11-26T10:00:00",
        },
        headers=headers,
    )
    event_id = created.json()["id"]
    client.post(f"/backoffice/events/{event_id}/publish", headers=headers)

    from fastapi.testclient import TestClient

    from app.main import app

    statuses = []
    for _ in range(7):
        with TestClient(app) as fresh_client:
            # each iteration uses a brand-new client -> no cookie sent ->
            # fresh anon_id every time, simulating a cookieless vote loop
            resp = fresh_client.post(f"/events/{event_id}/vote")
            statuses.append(resp.status_code)

    assert statuses[:5] == [200] * 5
    assert 429 in statuses[5:]

    final = client.get(f"/events/{event_id}")
    assert final.json()["likes_count"] == 5


def test_vote_returns_404_for_unpublished_event(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events", json={"source_url": "https://example.com/f9"}, headers=headers
    )
    event_id = created.json()["id"]
    response = client.post(f"/events/{event_id}/vote")
    assert response.status_code == 404


def test_view_permanent_returns_only_permanent_events(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    dated = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/vp1", "titre": "Dated", "date": "2026-12-01T10:00:00"},
        headers=headers,
    ).json()
    permanent = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/vp2", "titre": "Permanent", "is_permanent": True},
        headers=headers,
    ).json()
    client.post(f"/backoffice/events/{dated['id']}/publish", headers=headers)
    client.post(f"/backoffice/events/{permanent['id']}/publish", headers=headers)

    response = client.get("/events", params={"view": "permanent"})
    ids = [item["id"] for item in response.json()["items"]]
    assert permanent["id"] in ids
    assert dated["id"] not in ids


def test_view_calendar_excludes_permanent_and_filters_month(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    in_month = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/vc1", "titre": "In", "date": "2026-12-15T10:00:00"},
        headers=headers,
    ).json()
    out_of_month = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/vc2", "titre": "Out", "date": "2027-01-15T10:00:00"},
        headers=headers,
    ).json()
    permanent = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/vc3", "titre": "Perm", "is_permanent": True},
        headers=headers,
    ).json()
    for e in (in_month, out_of_month, permanent):
        client.post(f"/backoffice/events/{e['id']}/publish", headers=headers)

    response = client.get("/events", params={"view": "calendar", "month": 12, "year": 2026})
    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [in_month["id"]]


def test_view_week_includes_lower_bound_excludes_beyond(client, redacteur_token, monkeypatch):
    import app.routers.events_public as events_public_module
    from datetime import datetime, timezone

    fixed_now = datetime(2026, 12, 10, 8, 0, 0, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(events_public_module, "datetime", FixedDatetime)

    headers = {"Authorization": f"Bearer {redacteur_token}"}
    today_event = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/vw1", "titre": "Today", "date": "2026-12-10T00:00:00"},
        headers=headers,
    ).json()
    beyond_event = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/vw2", "titre": "Beyond", "date": "2026-12-18T00:00:00"},
        headers=headers,
    ).json()
    for e in (today_event, beyond_event):
        client.post(f"/backoffice/events/{e['id']}/publish", headers=headers)

    response = client.get("/events", params={"view": "week"})
    ids = [item["id"] for item in response.json()["items"]]
    assert today_event["id"] in ids
    assert beyond_event["id"] not in ids


def test_calendar_and_week_bounds_are_naive(client, session, monkeypatch):
    """Regression test for the tz-aware-vs-naive bound bug.

    Event.date is a NAIVE column (local time as entered by the user, never
    UTC). On SQLite, binding a tz-aware datetime against a naive column
    silently drops the tzinfo at the DBAPI level, so SQLite can never catch
    this bug just by checking query *results* — the old buggy code (which
    built bounds with `tzinfo=timezone.utc`) and the fixed code return the
    same rows against this test DB. On Postgres, comparing a naive column to
    a tz-aware bound makes Postgres implicitly convert the naive value using
    the session TimeZone setting before comparing, which silently shifts
    events across month/day boundaries whenever that session timezone isn't
    UTC.

    So rather than reconstructing the bounds independently (which the prior
    version of this test did, making it pass against the old buggy code just
    as well), this test drives the bounds through the REAL code path: it
    calls the actual GET /events endpoints via the test client, with the
    session's `exec` intercepted to capture the exact SQLAlchemy statement
    `list_events` builds, and asserts — via literal-bind compilation, which
    renders a tz-aware datetime as "... +00:00" and a naive one without any
    offset suffix — that the date-comparison bound literals in that captured
    statement carry no tzinfo. This fails if someone reverts the
    `tzinfo=timezone.utc` removal in events_public.py, because the captured
    statement would then contain an aware literal.
    """
    import app.routers.events_public as events_public_module
    from datetime import datetime, timezone
    from sqlmodel import Session as SQLModelSession

    fixed_now = datetime(2026, 12, 10, 8, 0, 0, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(events_public_module, "datetime", FixedDatetime)

    captured_statements = []
    original_exec = SQLModelSession.exec

    def capturing_exec(self, statement, *args, **kwargs):
        captured_statements.append(statement)
        return original_exec(self, statement, *args, **kwargs)

    monkeypatch.setattr(SQLModelSession, "exec", capturing_exec)

    def literal_sql(statement) -> str:
        return str(statement.compile(compile_kwargs={"literal_binds": True}))

    # Calendar view: month/year omitted, so bounds are derived from "now".
    captured_statements.clear()
    response = client.get("/events", params={"view": "calendar"})
    assert response.status_code == 200
    calendar_sql = "\n".join(literal_sql(stmt) for stmt in captured_statements)
    assert "event.date" in calendar_sql
    assert "+00:00" not in calendar_sql

    # Week view: bounds are always derived from "now".
    captured_statements.clear()
    response = client.get("/events", params={"view": "week"})
    assert response.status_code == 200
    week_sql = "\n".join(literal_sql(stmt) for stmt in captured_statements)
    assert "event.date" in week_sql
    assert "+00:00" not in week_sql


def test_view_mixed_unpaginated_views_ignore_page_size(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    for i in range(3):
        created = client.post(
            "/backoffice/events",
            json={"source_url": f"https://example.com/vm{i}", "titre": f"P{i}", "is_permanent": True},
            headers=headers,
        ).json()
        client.post(f"/backoffice/events/{created['id']}/publish", headers=headers)

    response = client.get("/events", params={"view": "permanent", "page_size": 1})
    assert len(response.json()["items"]) == 3


def test_mixed_default_sort_interleaves_permanent_events(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    dated_ids = []
    for i in range(6):
        created = client.post(
            "/backoffice/events",
            json={
                "source_url": f"https://example.com/il{i}",
                "titre": f"D{i}",
                "date": f"2026-12-{i + 1:02d}T10:00:00",
            },
            headers=headers,
        ).json()
        client.post(f"/backoffice/events/{created['id']}/publish", headers=headers)
        dated_ids.append(created["id"])

    permanent = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/ilp", "titre": "Perm", "is_permanent": True},
        headers=headers,
    ).json()
    client.post(f"/backoffice/events/{permanent['id']}/publish", headers=headers)

    response = client.get("/events", params={"page_size": 10})
    ids = [item["id"] for item in response.json()["items"]]
    # One permanent event is inserted after every 5 dated events: with 6
    # dated events, the permanent event lands at index 5 (after the first
    # chunk of 5 dated events, before the 6th dated event). This exact
    # position pins the real interleave algorithm and fails against a
    # plain date sort regardless of how the test DB orders NULL dates.
    assert ids[5] == permanent["id"]


def test_mixed_sort_single_permanent_event_not_repeated_across_many_dated(
    client, redacteur_token
):
    # Regression for the round-robin interleave bug: with few permanents
    # relative to many dated events, `permanent_index % permanent_total`
    # wrapped around and re-inserted the SAME permanent event multiple times
    # in one page (e.g. 1 permanent + 15 dated -> permanent appears 3 times),
    # producing duplicate event ids in the response (duplicate React keys on
    # the frontend). Each permanent event must appear at most once.
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    dated_ids = []
    for i in range(15):
        created = client.post(
            "/backoffice/events",
            json={
                "source_url": f"https://example.com/norepeat{i}",
                "titre": f"D{i}",
                "date": f"2026-12-{i + 1:02d}T10:00:00",
            },
            headers=headers,
        ).json()
        client.post(f"/backoffice/events/{created['id']}/publish", headers=headers)
        dated_ids.append(created["id"])

    permanent = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/norepeatp", "titre": "Perm", "is_permanent": True},
        headers=headers,
    ).json()
    client.post(f"/backoffice/events/{permanent['id']}/publish", headers=headers)

    response = client.get("/events", params={"page_size": 20})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert ids.count(permanent["id"]) == 1
    # Nothing dropped either: all 15 dated events plus the one permanent.
    assert len(ids) == 16
    for dated_id in dated_ids:
        assert ids.count(dated_id) == 1


def test_list_events_rejects_invalid_view(client):
    response = client.get("/events", params={"view": "bogus"})
    assert response.status_code == 422


def test_list_events_rejects_out_of_range_month(client):
    response = client.get("/events", params={"view": "calendar", "month": 13})
    assert response.status_code == 422


def test_mixed_sort_with_no_permanent_events_is_plain_date_order(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/nopermanent", "titre": "Only dated", "date": "2026-12-01T10:00:00"},
        headers=headers,
    ).json()
    client.post(f"/backoffice/events/{created['id']}/publish", headers=headers)
    response = client.get("/events")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [created["id"]]
