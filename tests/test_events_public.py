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


def test_vote_returns_404_for_unpublished_event(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events", json={"source_url": "https://example.com/f9"}, headers=headers
    )
    event_id = created.json()["id"]
    response = client.post(f"/events/{event_id}/vote")
    assert response.status_code == 404
