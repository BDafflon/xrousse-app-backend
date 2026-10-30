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
