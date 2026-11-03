import pytest


@pytest.fixture(name="published_event_id")
def published_event_id_fixture(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/saved1",
            "titre": "Fete",
            "date": "2099-11-20T10:00:00",
        },
        headers=headers,
    )
    event_id = created.json()["id"]
    client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    return event_id


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_requires_auth(client, published_event_id):
    assert client.get("/saved-events").status_code == 401
    assert client.put(f"/saved-events/{published_event_id}").status_code == 401
    assert client.delete(f"/saved-events/{published_event_id}").status_code == 401


def test_save_then_list(client, lecteur_token, published_event_id):
    response = client.put(f"/saved-events/{published_event_id}", headers=_auth(lecteur_token))
    assert response.status_code == 204

    listed = client.get("/saved-events", headers=_auth(lecteur_token))
    assert listed.status_code == 200
    assert [e["id"] for e in listed.json()] == [published_event_id]


def test_save_is_idempotent(client, lecteur_token, published_event_id):
    headers = _auth(lecteur_token)
    assert client.put(f"/saved-events/{published_event_id}", headers=headers).status_code == 204
    assert client.put(f"/saved-events/{published_event_id}", headers=headers).status_code == 204
    assert len(client.get("/saved-events", headers=headers).json()) == 1


def test_unsave(client, lecteur_token, published_event_id):
    headers = _auth(lecteur_token)
    client.put(f"/saved-events/{published_event_id}", headers=headers)
    assert client.delete(f"/saved-events/{published_event_id}", headers=headers).status_code == 204
    assert client.get("/saved-events", headers=headers).json() == []
    # unsaving again is a no-op
    assert client.delete(f"/saved-events/{published_event_id}", headers=headers).status_code == 204


def test_saved_events_are_per_user(client, lecteur_token, other_lecteur_token, published_event_id):
    client.put(f"/saved-events/{published_event_id}", headers=_auth(lecteur_token))
    assert client.get("/saved-events", headers=_auth(other_lecteur_token)).json() == []


def test_save_unknown_or_draft_event_404(client, lecteur_token, redacteur_token):
    headers = _auth(lecteur_token)
    assert client.put("/saved-events/9999", headers=headers).status_code == 404

    draft = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/draft-saved"},
        headers=_auth(redacteur_token),
    ).json()
    assert client.put(f"/saved-events/{draft['id']}", headers=headers).status_code == 404


def test_unpublished_saved_event_hidden(client, lecteur_token, redacteur_token, published_event_id):
    client.put(f"/saved-events/{published_event_id}", headers=_auth(lecteur_token))
    client.post(
        f"/backoffice/events/{published_event_id}/unpublish", headers=_auth(redacteur_token)
    )
    assert client.get("/saved-events", headers=_auth(lecteur_token)).json() == []
