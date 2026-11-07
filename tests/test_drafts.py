def test_upsert_creates_new_draft(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post("/drafts/upsert", json={"source_url": "https://example.com/a"}, headers=headers)
    assert response.status_code == 201
    assert response.json()["statut"] == "brouillon"


def test_upsert_resumes_existing_draft_by_source_url(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    first = client.post("/drafts/upsert", json={"source_url": "https://example.com/b"}, headers=headers)
    second = client.post("/drafts/upsert", json={"source_url": "https://example.com/b"}, headers=headers)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


def test_patch_title(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft = client.post("/drafts/upsert", json={"source_url": "https://example.com/c"}, headers=headers).json()
    response = client.patch(f"/drafts/{draft['id']}/title", json={"titre": "Brocante du quartier"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["titre"] == "Brocante du quartier"


def test_append_description_appends_not_replaces(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft = client.post("/drafts/upsert", json={"source_url": "https://example.com/d"}, headers=headers).json()
    client.patch(f"/drafts/{draft['id']}/append-description", json={"text": "Premier paragraphe"}, headers=headers)
    response = client.patch(f"/drafts/{draft['id']}/append-description", json={"text": "Deuxieme paragraphe"}, headers=headers)
    assert "Premier paragraphe" in response.json()["description"]
    assert "Deuxieme paragraphe" in response.json()["description"]


def test_upsert_rejects_lecteur(client, lecteur_token):
    headers = {"Authorization": f"Bearer {lecteur_token}"}
    response = client.post("/drafts/upsert", json={"source_url": "https://example.com/z"}, headers=headers)
    assert response.status_code == 403


def test_upsert_unauthenticated(client):
    response = client.post("/drafts/upsert", json={"source_url": "https://example.com/z2"})
    assert response.status_code == 401


def test_patch_title_404(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.patch("/drafts/9999/title", json={"titre": "x"}, headers=headers)
    assert response.status_code == 404


def test_append_description_first_call_no_leading_separator(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft = client.post("/drafts/upsert", json={"source_url": "https://example.com/e"}, headers=headers).json()
    response = client.patch(f"/drafts/{draft['id']}/append-description", json={"text": "Seul paragraphe"}, headers=headers)
    assert response.json()["description"] == "Seul paragraphe"


def test_patch_source_updates_url(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft = client.post("/drafts/upsert", json={"source_url": "https://example.com/f1"}, headers=headers).json()
    response = client.patch(
        f"/drafts/{draft['id']}/source", json={"source_url": "https://example.com/f2"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["source_url"] == "https://example.com/f2"


def test_patch_source_conflict_with_other_event(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft_a = client.post("/drafts/upsert", json={"source_url": "https://example.com/g1"}, headers=headers).json()
    draft_b = client.post("/drafts/upsert", json={"source_url": "https://example.com/g2"}, headers=headers).json()
    response = client.patch(
        f"/drafts/{draft_b['id']}/source", json={"source_url": "https://example.com/g1"}, headers=headers
    )
    assert response.status_code == 409


def test_patch_title_409_if_event_already_published(client, redacteur_token):
    # Regression for I2: draft endpoints are restricted to brouillon-status
    # events, so a published event's titre can't be nulled/altered via a
    # draft endpoint called on its id.
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post(
        "/backoffice/events",
        json={
            "source_url": "https://example.com/draftpub1",
            "titre": "Titre valide",
            "date": "2026-11-15T10:00:00",
        },
        headers=headers,
    ).json()
    client.post(f"/backoffice/events/{created['id']}/publish", headers=headers)

    response = client.patch(
        f"/drafts/{created['id']}/title", json={"titre": None}, headers=headers
    )
    assert response.status_code == 409


def test_patch_source_same_url_is_noop_not_conflict(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft = client.post("/drafts/upsert", json={"source_url": "https://example.com/h"}, headers=headers).json()
    response = client.patch(
        f"/drafts/{draft['id']}/source", json={"source_url": "https://example.com/h"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["source_url"] == "https://example.com/h"


def test_patch_image_updates_url(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft = client.post("/drafts/upsert", json={"source_url": "https://example.com/i"}, headers=headers).json()
    response = client.patch(
        f"/drafts/{draft['id']}/image", json={"image_url": "/uploads/events/abc.jpg"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["image_url"] == "/uploads/events/abc.jpg"


def test_patch_image_404(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.patch("/drafts/9999/image", json={"image_url": "/uploads/events/abc.jpg"}, headers=headers)
    assert response.status_code == 404


def test_patch_date_updates_date(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft = client.post("/drafts/upsert", json={"source_url": "https://example.com/j"}, headers=headers).json()
    response = client.patch(
        f"/drafts/{draft['id']}/date", json={"date": "2026-11-15T19:00:00"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["date"] == "2026-11-15T19:00:00"


def test_patch_date_fin_updates_date_fin(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft = client.post("/drafts/upsert", json={"source_url": "https://example.com/k"}, headers=headers).json()
    client.patch(f"/drafts/{draft['id']}/date", json={"date": "2026-11-15T19:00:00"}, headers=headers)
    response = client.patch(
        f"/drafts/{draft['id']}/date-fin", json={"date_fin": "2026-11-16T23:00:00"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["date_fin"] == "2026-11-16T23:00:00"


def test_patch_date_fin_without_date_is_ok_on_draft(client, redacteur_token):
    # Unlike EventCreate, a draft PATCH allows date_fin to be set before date
    # has ever been captured (the extension may receive it in either order);
    # only the date/date_fin ordering itself is validated once both are set.
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft = client.post("/drafts/upsert", json={"source_url": "https://example.com/l"}, headers=headers).json()
    response = client.patch(
        f"/drafts/{draft['id']}/date-fin", json={"date_fin": "2026-11-16T23:00:00"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["date_fin"] == "2026-11-16T23:00:00"


def test_patch_date_fin_before_date_rejected(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft = client.post("/drafts/upsert", json={"source_url": "https://example.com/m"}, headers=headers).json()
    client.patch(f"/drafts/{draft['id']}/date", json={"date": "2026-11-15T19:00:00"}, headers=headers)
    response = client.patch(
        f"/drafts/{draft['id']}/date-fin", json={"date_fin": "2026-11-10T23:00:00"}, headers=headers
    )
    assert response.status_code == 422


def test_patch_date_404(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.patch("/drafts/9999/date", json={"date": "2026-11-15T19:00:00"}, headers=headers)
    assert response.status_code == 404


def test_patch_draft_prix_single_range_clear_and_invalid(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    draft = client.post("/drafts/upsert", json={"source_url": "https://example.com/prix"}, headers=headers).json()
    url = f"/drafts/{draft['id']}/prix"

    r = client.patch(url, json={"prix_min": 12}, headers=headers)
    assert r.status_code == 200
    assert (r.json()["prix_min"], r.json()["prix_max"]) == (12, None)

    r = client.patch(url, json={"prix_min": 5, "prix_max": 10}, headers=headers)
    assert (r.json()["prix_min"], r.json()["prix_max"]) == (5, 10)

    assert client.patch(url, json={"prix_min": 10, "prix_max": 5}, headers=headers).status_code == 422
    assert client.patch(url, json={"prix_max": 5}, headers=headers).status_code == 422
    assert client.patch(url, json={"prix_min": -3}, headers=headers).status_code == 422

    r = client.patch(url, json={"prix_min": None, "prix_max": None}, headers=headers)
    assert (r.json()["prix_min"], r.json()["prix_max"]) == (None, None)
    assert client.patch("/drafts/9999/prix", json={"prix_min": 1}, headers=headers).status_code == 404
