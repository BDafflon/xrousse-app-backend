from app.routers.events_me import MAX_PENDING_PROPOSALS


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _payload(**kw):
    return {"titre": "Ma sortie", "date": "2026-12-01T10:00:00", **kw}


def test_requires_auth(client):
    assert client.get("/me/events").status_code == 401
    assert client.post("/me/events", json=_payload()).status_code == 401


def test_private_event_stays_draft_and_hidden(client, lecteur_token):
    r = client.post("/me/events", json=_payload(visibilite="prive"), headers=_h(lecteur_token))
    assert r.status_code == 201
    body = r.json()
    assert body["statut"] == "brouillon" and body["visibilite"] == "prive"
    assert body["source_url"].startswith("user-event:")

    assert client.get("/events").json()["items"] == []
    assert client.get(f"/events/{body['id']}").status_code == 404
    assert client.get("/me/events", headers=_h(lecteur_token)).json()[0]["id"] == body["id"]


def test_private_event_invisible_to_others_and_redacteur(
    client, lecteur_token, other_lecteur_token, redacteur_token
):
    eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
    assert client.get(f"/me/events/{eid}", headers=_h(other_lecteur_token)).status_code == 404
    assert client.patch(f"/me/events/{eid}", json={"titre": "x"}, headers=_h(other_lecteur_token)).status_code == 404
    assert client.delete(f"/me/events/{eid}", headers=_h(other_lecteur_token)).status_code == 404
    assert client.get(f"/backoffice/events/{eid}", headers=_h(redacteur_token)).status_code == 404
    assert client.get("/backoffice/events", headers=_h(redacteur_token)).json() == []


def test_admin_sees_and_moderates_private_events(client, lecteur_token, admin_token):
    eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
    assert client.get(f"/backoffice/events/{eid}", headers=_h(admin_token)).json()["visibilite"] == "prive"
    assert [e["id"] for e in client.get("/backoffice/events", headers=_h(admin_token)).json()] == [eid]
    # but a private event can never be published
    assert client.post(f"/backoffice/events/{eid}/publish", headers=_h(admin_token)).status_code == 409
    assert client.get("/events").json()["items"] == []
    # admin can remove inappropriate content
    assert client.delete(f"/backoffice/events/{eid}", headers=_h(admin_token)).status_code == 204


def test_share_private_event(client, lecteur_token, other_lecteur_token):
    eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
    other = _h(other_lecteur_token)
    assert client.get(f"/me/events/{eid}", headers=other).status_code == 404

    r = client.post(f"/me/events/{eid}/shares", json={"email": "Other-Lecteur@test.com"}, headers=_h(lecteur_token))
    assert r.status_code == 201
    uid = r.json()["user_id"]
    # idempotent
    assert client.post(f"/me/events/{eid}/shares", json={"email": "other-lecteur@test.com"}, headers=_h(lecteur_token)).status_code == 201

    assert client.get(f"/me/events/{eid}", headers=other).status_code == 200
    assert [e["id"] for e in client.get("/me/events/shared-with-me", headers=other).json()] == [eid]
    # read-only for the recipient
    assert client.patch(f"/me/events/{eid}", json={"titre": "x"}, headers=other).status_code == 404
    assert client.delete(f"/me/events/{eid}", headers=other).status_code == 404
    assert client.get(f"/me/events/{eid}/shares", headers=other).status_code == 404
    assert client.post(f"/me/events/{eid}/shares", json={"email": "lecteur@test.com"}, headers=other).status_code == 404
    # still not in own events / public
    assert client.get("/me/events", headers=other).json() == []
    assert client.get("/events").json()["items"] == []

    assert [s["user_id"] for s in client.get(f"/me/events/{eid}/shares", headers=_h(lecteur_token)).json()] == [uid]
    assert client.delete(f"/me/events/{eid}/shares/{uid}", headers=_h(lecteur_token)).status_code == 204
    assert client.get(f"/me/events/{eid}", headers=other).status_code == 404


def test_recipient_can_leave_shared_event(client, lecteur_token, other_lecteur_token):
    eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
    uid = client.post(f"/me/events/{eid}/shares", json={"email": "other-lecteur@test.com"}, headers=_h(lecteur_token)).json()["user_id"]
    assert client.delete(f"/me/events/{eid}/shares/{uid}", headers=_h(other_lecteur_token)).status_code == 204
    assert client.get("/me/events/shared-with-me", headers=_h(other_lecteur_token)).json() == []


def test_third_party_cannot_revoke_share(client, lecteur_token, other_lecteur_token, redacteur_token):
    eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
    uid = client.post(f"/me/events/{eid}/shares", json={"email": "other-lecteur@test.com"}, headers=_h(lecteur_token)).json()["user_id"]
    assert client.delete(f"/me/events/{eid}/shares/{uid}", headers=_h(redacteur_token)).status_code == 404
    assert client.get(f"/me/events/{eid}", headers=_h(other_lecteur_token)).status_code == 200


def test_share_validation(client, lecteur_token):
    h = _h(lecteur_token)
    priv = client.post("/me/events", json=_payload(), headers=h).json()["id"]
    pub = client.post("/me/events", json=_payload(visibilite="public"), headers=h).json()["id"]
    assert client.post(f"/me/events/{priv}/shares", json={"email": "nobody@test.com"}, headers=h).status_code == 404
    assert client.post(f"/me/events/{priv}/shares", json={"email": "lecteur@test.com"}, headers=h).status_code == 422
    assert client.post(f"/me/events/{pub}/shares", json={"email": "lecteur@test.com"}, headers=h).status_code == 409


def test_going_public_revokes_shares(client, lecteur_token, other_lecteur_token):
    h = _h(lecteur_token)
    eid = client.post("/me/events", json=_payload(), headers=h).json()["id"]
    client.post(f"/me/events/{eid}/shares", json={"email": "other-lecteur@test.com"}, headers=h)
    client.patch(f"/me/events/{eid}", json={"visibilite": "public"}, headers=h)
    client.patch(f"/me/events/{eid}", json={"visibilite": "prive"}, headers=h)
    assert client.get(f"/me/events/{eid}", headers=_h(other_lecteur_token)).status_code == 404


def test_deleting_shared_event_and_recipient(client, session, lecteur_token, other_lecteur_token, admin_token):
    h = _h(lecteur_token)
    eid = client.post("/me/events", json=_payload(), headers=h).json()["id"]
    uid = client.post(f"/me/events/{eid}/shares", json={"email": "other-lecteur@test.com"}, headers=h).json()["user_id"]
    # admin deletes the recipient account: shares go with it
    assert client.delete(f"/backoffice/users/{uid}", headers=_h(admin_token)).status_code == 204
    assert client.get(f"/me/events/{eid}/shares", headers=h).json() == []
    # owner deletes an event that is still shared
    eid2 = client.post("/me/events", json=_payload(), headers=h).json()["id"]
    client.post(f"/me/events/{eid2}/shares", json={"email": "admin@test.com"}, headers=h)
    assert client.delete(f"/me/events/{eid2}", headers=h).status_code == 204


def test_public_proposal_goes_to_moderation(client, lecteur_token):
    r = client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token))
    assert r.status_code == 201
    assert r.json()["statut"] == "en_moderation"
    assert client.get("/events").json()["items"] == []


def test_public_proposal_requires_date(client, lecteur_token):
    r = client.post("/me/events", json={"titre": "x", "visibilite": "public"}, headers=_h(lecteur_token))
    assert r.status_code == 422


def test_moderation_is_admin_only(client, lecteur_token, redacteur_token):
    for token in (lecteur_token, redacteur_token):
        assert client.get("/backoffice/moderation/events", headers=_h(token)).status_code == 403


def test_approve_publishes(client, lecteur_token, admin_token):
    eid = client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token)).json()["id"]
    queue = client.get("/backoffice/moderation/events", headers=_h(admin_token)).json()
    assert [e["id"] for e in queue] == [eid]
    assert queue[0]["created_by_email"] == "lecteur@test.com"

    r = client.post(f"/backoffice/moderation/events/{eid}/approve", headers=_h(admin_token))
    assert r.status_code == 200 and r.json()["statut"] == "publie"
    assert [e["id"] for e in client.get("/events").json()["items"]] == [eid]
    # no longer pending
    assert client.post(f"/backoffice/moderation/events/{eid}/approve", headers=_h(admin_token)).status_code == 404


def test_reject_requires_motif_and_hides(client, lecteur_token, admin_token):
    eid = client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token)).json()["id"]
    url = f"/backoffice/moderation/events/{eid}/reject"
    assert client.post(url, json={"motif": "  "}, headers=_h(admin_token)).status_code == 422
    r = client.post(url, json={"motif": "Doublon"}, headers=_h(admin_token))
    assert r.json()["statut"] == "refuse"
    assert client.get("/events").json()["items"] == []
    mine = client.get(f"/me/events/{eid}", headers=_h(lecteur_token)).json()
    assert mine["statut"] == "refuse" and mine["motif_refus"] == "Doublon"


def test_edit_resubmits_to_moderation(client, lecteur_token, admin_token):
    eid = client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token)).json()["id"]
    client.post(f"/backoffice/moderation/events/{eid}/approve", headers=_h(admin_token))
    r = client.patch(f"/me/events/{eid}", json={"titre": "Autre"}, headers=_h(lecteur_token))
    assert r.json()["statut"] == "en_moderation"
    assert client.get("/events").json()["items"] == []


def test_visibility_switch(client, lecteur_token):
    eid = client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token)).json()["id"]
    r = client.patch(f"/me/events/{eid}", json={"visibilite": "prive"}, headers=_h(lecteur_token))
    assert r.json()["statut"] == "brouillon"
    r = client.patch(f"/me/events/{eid}", json={"visibilite": "public"}, headers=_h(lecteur_token))
    assert r.json()["statut"] == "en_moderation"


def test_redacteur_cannot_publish_pending_proposal(client, lecteur_token, redacteur_token):
    eid = client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token)).json()["id"]
    r = client.post(f"/backoffice/events/{eid}/publish", headers=_h(redacteur_token))
    assert r.status_code == 403


def test_pending_cap(client, lecteur_token):
    for _ in range(MAX_PENDING_PROPOSALS):
        assert client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token)).status_code == 201
    r = client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token))
    assert r.status_code == 429
    # private events are not capped
    assert client.post("/me/events", json=_payload(visibilite="prive"), headers=_h(lecteur_token)).status_code == 201


def test_delete_own_event(client, lecteur_token):
    eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
    assert client.delete(f"/me/events/{eid}", headers=_h(lecteur_token)).status_code == 204
    assert client.get(f"/me/events/{eid}", headers=_h(lecteur_token)).status_code == 404


def test_delete_published_event_saved_by_someone(client, lecteur_token, other_lecteur_token, admin_token):
    eid = client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token)).json()["id"]
    client.post(f"/backoffice/moderation/events/{eid}/approve", headers=_h(admin_token))
    client.put(f"/saved-events/{eid}", headers=_h(other_lecteur_token))
    assert client.delete(f"/me/events/{eid}", headers=_h(lecteur_token)).status_code == 204
