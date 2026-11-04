def test_create_event_as_redacteur(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post("/backoffice/events", json={"source_url": "https://example.com/e1"}, headers=headers)
    assert response.status_code == 201
    assert response.json()["statut"] == "brouillon"


def test_create_event_rejects_lecteur(client, lecteur_token):
    headers = {"Authorization": f"Bearer {lecteur_token}"}
    response = client.post("/backoffice/events", json={"source_url": "https://example.com/e1"}, headers=headers)
    assert response.status_code == 403


def test_publish_requires_titre_and_date(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post("/backoffice/events", json={"source_url": "https://example.com/e2"}, headers=headers)
    event_id = created.json()["id"]
    response = client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    assert response.status_code == 422


def test_publish_succeeds_with_titre_and_date(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post("/backoffice/events", json={
        "source_url": "https://example.com/e3", "titre": "Vide grenier", "date": "2026-11-15T10:00:00"
    }, headers=headers)
    event_id = created.json()["id"]
    response = client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    assert response.status_code == 200
    assert response.json()["statut"] == "publie"


def test_publish_succeeds_even_if_alerts_fail(client, redacteur_token, monkeypatch):
    # trigger_immediate_alerts is called synchronously from inside publish;
    # if it blows up (e.g. Resend down), publication must still succeed.
    def boom(*args, **kwargs):
        raise Exception("alerts exploded")

    monkeypatch.setattr(
        "app.routers.events_backoffice.trigger_immediate_alerts", boom
    )
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post("/backoffice/events", json={
        "source_url": "https://example.com/e3b", "titre": "Vide grenier", "date": "2026-11-15T10:00:00"
    }, headers=headers)
    event_id = created.json()["id"]
    response = client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    assert response.status_code == 200
    assert response.json()["statut"] == "publie"


def test_feature_toggle(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post("/backoffice/events", json={"source_url": "https://example.com/e4"}, headers=headers)
    event_id = created.json()["id"]
    response = client.post(f"/backoffice/events/{event_id}/feature", headers=headers)
    assert response.status_code == 200
    assert response.json()["featured_editorial"] is True


def test_patch_updates_fields(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post("/backoffice/events", json={"source_url": "https://example.com/e5"}, headers=headers)
    event_id = created.json()["id"]
    response = client.patch(f"/backoffice/events/{event_id}", json={"titre": "Nouveau titre"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["titre"] == "Nouveau titre"


def test_delete_event(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post("/backoffice/events", json={"source_url": "https://example.com/e6"}, headers=headers)
    event_id = created.json()["id"]
    response = client.delete(f"/backoffice/events/{event_id}", headers=headers)
    assert response.status_code == 204


def test_delete_event_is_soft_and_restorable(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events", json={"source_url": "https://example.com/e6-soft"}, headers=headers
    )
    event_id = created.json()["id"]

    client.delete(f"/backoffice/events/{event_id}", headers=headers)

    # The event still exists (soft-deleted) and is directly fetchable...
    detail = client.get(f"/backoffice/events/{event_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["is_deleted"] is True

    # ...but is excluded from the default (non-trash) list.
    listing = client.get("/backoffice/events", headers=headers)
    assert event_id not in [e["id"] for e in listing.json()]

    # It reappears when explicitly including deleted events.
    listing_with_deleted = client.get("/backoffice/events?include_deleted=true", headers=headers)
    assert event_id in [e["id"] for e in listing_with_deleted.json()]

    restored = client.post(f"/backoffice/events/{event_id}/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["is_deleted"] is False

    listing_after_restore = client.get("/backoffice/events", headers=headers)
    assert event_id in [e["id"] for e in listing_after_restore.json()]


def test_restore_event_404(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post("/backoffice/events/9999/restore", headers=headers)
    assert response.status_code == 404


def test_get_event_detail(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post("/backoffice/events", json={"source_url": "https://example.com/e7"}, headers=headers)
    event_id = created.json()["id"]
    response = client.get(f"/backoffice/events/{event_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == event_id


def test_get_event_detail_404(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.get("/backoffice/events/9999", headers=headers)
    assert response.status_code == 404


def test_patch_event_404(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.patch("/backoffice/events/9999", json={"titre": "x"}, headers=headers)
    assert response.status_code == 404


def test_list_events_paginated(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    for i in range(3):
        client.post("/backoffice/events", json={"source_url": f"https://example.com/list{i}"}, headers=headers)
    response = client.get("/backoffice/events?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_events_rejects_lecteur(client, lecteur_token):
    headers = {"Authorization": f"Bearer {lecteur_token}"}
    response = client.get("/backoffice/events", headers=headers)
    assert response.status_code == 403


def test_create_event_with_tags(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    tags_response = client.get("/tags")
    tag_id = tags_response.json()[0]["id"]
    response = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/e8", "tag_ids": [tag_id]},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["tags"][0]["id"] == tag_id


def test_create_event_unauthenticated(client):
    response = client.post("/backoffice/events", json={"source_url": "https://example.com/e9"})
    assert response.status_code == 401


def test_delete_event_with_vote_succeeds(client, redacteur_token):
    # Deleting an event that has a vote must still succeed. This was
    # originally a regression test for a 500 under hard delete (vote.event_id
    # has no ON DELETE rule); delete is now a soft delete (sets is_deleted),
    # which never touches the vote rows at all.
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/del1",
            "titre": "A supprimer",
            "date": "2026-11-15T10:00:00",
        },
        headers=headers,
    )
    event_id = created.json()["id"]
    client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    vote_response = client.post(f"/events/{event_id}/vote")
    assert vote_response.status_code == 200

    response = client.delete(f"/backoffice/events/{event_id}", headers=headers)
    assert response.status_code == 204


def test_patch_rejects_nulling_titre_on_published_event(client, redacteur_token):
    # Regression for I2: PATCH must not be able to null titre/date on an
    # already-published event, bypassing the publish-time validation rule.
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/pub1",
            "titre": "Titre valide",
            "date": "2026-11-15T10:00:00",
        },
        headers=headers,
    )
    event_id = created.json()["id"]
    client.post(f"/backoffice/events/{event_id}/publish", headers=headers)

    response = client.patch(
        f"/backoffice/events/{event_id}", json={"titre": None}, headers=headers
    )
    assert response.status_code == 422


def test_unpublish_moves_event_back_to_brouillon(client, redacteur_token):
    # Regression for I2: unpublish endpoint exists and the event no longer
    # appears in the public listing afterward.
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/unpub1",
            "titre": "Titre valide",
            "date": "2026-11-15T10:00:00",
        },
        headers=headers,
    )
    event_id = created.json()["id"]
    client.post(f"/backoffice/events/{event_id}/publish", headers=headers)

    response = client.post(
        f"/backoffice/events/{event_id}/unpublish", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["statut"] == "brouillon"

    public_list = client.get("/events")
    ids = [item["id"] for item in public_list.json()["items"]]
    assert event_id not in ids


def test_unpublish_404_if_missing(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post("/backoffice/events/9999/unpublish", headers=headers)
    assert response.status_code == 404


def test_create_event_rejects_timezone_aware_date(client, redacteur_token):
    # Event.date is typed NaiveDatetime, which rejects tz-aware ISO strings outright
    # (422) rather than silently accepting/normalizing the offset. This test pins
    # that behavior so a future change (e.g. switching to plain `datetime`) that
    # silently accepts aware timestamps would be caught as a regression.
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/e10",
            "titre": "Vide grenier",
            "date": "2026-11-15T10:00:00+01:00",
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_create_event_defaults_is_permanent_false(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events", json={"source_url": "https://example.com/perm1"}, headers=headers
    )
    assert created.json()["is_permanent"] is False


def test_publish_permanent_event_without_date_succeeds(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/perm2",
            "titre": "Expo permanente",
            "is_permanent": True,
        },
        headers=headers,
    )
    event_id = created.json()["id"]
    response = client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    assert response.status_code == 200
    assert response.json()["statut"] == "publie"


def test_publish_event_without_date_or_permanent_still_422(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/perm3", "titre": "Sans date"},
        headers=headers,
    )
    event_id = created.json()["id"]
    response = client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    assert response.status_code == 422


def test_create_event_with_multi_day_and_recurrence_fields_persists(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/multi-day-1",
            "titre": "Marche de Noel",
            "date": "2026-12-05T10:00:00",
            "date_fin": "2026-12-08T18:00:00",
        },
        headers=headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["date_fin"] == "2026-12-08T18:00:00"
    assert body["recurrence_jours"] is None
    assert body["recurrence_fin"] is None


def test_create_event_rejects_date_fin_without_date(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/bad-1", "date_fin": "2026-12-08T18:00:00"},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "date_fin"


def test_create_event_rejects_date_fin_before_date(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/bad-2",
            "date": "2026-12-08T10:00:00",
            "date_fin": "2026-12-05T18:00:00",
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "date_fin"


def test_create_event_rejects_recurrence_without_date(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/bad-3", "recurrence_jours": "1,4"},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "recurrence_jours"


def test_create_event_rejects_recurrence_and_multi_day_range_together(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/bad-4",
            "date": "2026-12-05T19:00:00",
            "date_fin": "2026-12-08T23:00:00",
            "recurrence_jours": "1,4",
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "date_fin"


def test_create_event_rejects_recurrence_fin_before_date(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/bad-5",
            "date": "2026-12-08T19:00:00",
            "recurrence_jours": "1,4",
            "recurrence_fin": "2026-12-01T00:00:00",
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "recurrence_fin"


def test_create_event_rejects_invalid_recurrence_jours_values(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/bad-6",
            "date": "2026-12-08T19:00:00",
            "recurrence_jours": "1,1,8",
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "recurrence_jours"


def test_create_event_rejects_recurrence_fin_before_date_without_recurrence_jours(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/bad-7",
            "date": "2026-12-08T19:00:00",
            "recurrence_fin": "2026-12-01T00:00:00",
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "recurrence_fin"


def test_create_event_accepts_weekly_recurrence(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/good-1",
            "date": "2026-11-03T19:00:00",
            "date_fin": "2026-11-03T23:00:00",
            "recurrence_jours": "2,5",
            "recurrence_fin": "2026-11-30T00:00:00",
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["recurrence_jours"] == "2,5"


def test_patch_date_fin_only_succeeds_when_event_already_has_stored_date(
    client, redacteur_token
):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/patch-date-fin-only",
            "titre": "Expo",
            "date": "2026-12-05T10:00:00",
        },
        headers=headers,
    )
    event_id = created.json()["id"]

    response = client.patch(
        f"/backoffice/events/{event_id}",
        json={"date_fin": "2026-12-08T18:00:00"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["date_fin"] == "2026-12-08T18:00:00"


def test_patch_date_rejected_when_merged_state_violates_date_fin_order(
    client, redacteur_token
):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/patch-date-after-fin",
            "titre": "Expo2",
            "date": "2026-12-05T10:00:00",
            "date_fin": "2026-12-08T18:00:00",
        },
        headers=headers,
    )
    event_id = created.json()["id"]

    response = client.patch(
        f"/backoffice/events/{event_id}",
        json={"date": "2026-12-10T10:00:00"},
        headers=headers,
    )
    assert response.status_code == 422


def test_patch_merged_state_rejects_recurrence_plus_multi_day_range(
    client, redacteur_token
):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/patch-recurrence-plus-range",
            "titre": "Marche",
            "date": "2026-12-05T10:00:00",
            "recurrence_jours": "2,5",
        },
        headers=headers,
    )
    event_id = created.json()["id"]

    # Payload doesn't clear recurrence_jours, so the merged state ends up
    # with both a multi-day range AND recurrence set.
    response = client.patch(
        f"/backoffice/events/{event_id}",
        json={"date": "2026-12-05T10:00:00", "date_fin": "2026-12-06T18:00:00"},
        headers=headers,
    )
    assert response.status_code == 422
