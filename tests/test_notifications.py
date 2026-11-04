def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _payload(**kw):
    return {"titre": "Ma sortie", "date": "2026-12-01T10:00:00", **kw}


def _unread(client, token):
    return client.get("/me/notifications/unread-count", headers=_h(token)).json()["unread"]


def test_requires_auth(client):
    assert client.get("/me/notifications").status_code == 401


def test_public_proposal_notifies_admins_only(client, lecteur_token, admin_token, redacteur_token, sent_emails):
    client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token))
    assert _unread(client, admin_token) == 1
    assert _unread(client, lecteur_token) == 0
    assert _unread(client, redacteur_token) == 0
    n = client.get("/me/notifications", headers=_h(admin_token)).json()[0]
    assert n["type"] == "proposal_submitted" and n["link"] == "/admin/moderation"
    assert [m["to"] for m in sent_emails] == ["admin@test.com"]


def test_private_event_does_not_notify_admins(client, lecteur_token, admin_token, sent_emails):
    client.post("/me/events", json=_payload(), headers=_h(lecteur_token))
    assert _unread(client, admin_token) == 0
    assert sent_emails == []


def test_resubmission_notifies_again_but_pending_edit_does_not(client, lecteur_token, admin_token):
    eid = client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token)).json()["id"]
    client.patch(f"/me/events/{eid}", json={"titre": "Autre"}, headers=_h(lecteur_token))
    assert _unread(client, admin_token) == 1  # still pending: no duplicate
    client.post(f"/backoffice/moderation/events/{eid}/approve", headers=_h(admin_token))
    client.patch(f"/me/events/{eid}", json={"titre": "Encore"}, headers=_h(lecteur_token))
    assert _unread(client, admin_token) == 2


def test_approve_and_reject_notify_author(client, lecteur_token, admin_token, sent_emails):
    ok = client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token)).json()["id"]
    ko = client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token)).json()["id"]
    client.post(f"/backoffice/moderation/events/{ok}/approve", headers=_h(admin_token))
    client.post(f"/backoffice/moderation/events/{ko}/reject", json={"motif": "Doublon <b>"}, headers=_h(admin_token))
    types = {n["type"]: n for n in client.get("/me/notifications", headers=_h(lecteur_token)).json()}
    assert set(types) == {"proposal_approved", "proposal_rejected"}
    assert "Doublon" in types["proposal_rejected"]["message"]
    mails = [m for m in sent_emails if m["to"] == "lecteur@test.com"]
    assert len(mails) == 2
    # user-provided text is escaped in emails
    assert "<b>" not in "".join(m["html"] for m in mails)


def test_share_notifies_recipient_once(client, lecteur_token, other_lecteur_token, sent_emails):
    eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
    body = {"email": "other-lecteur@test.com"}
    client.post(f"/me/events/{eid}/shares", json=body, headers=_h(lecteur_token))
    client.post(f"/me/events/{eid}/shares", json=body, headers=_h(lecteur_token))
    assert _unread(client, other_lecteur_token) == 1
    assert client.get("/me/notifications", headers=_h(other_lecteur_token)).json()[0]["type"] == "event_shared"
    assert [m["to"] for m in sent_emails] == ["other-lecteur@test.com"]


def test_mark_read_and_read_all(client, lecteur_token, other_lecteur_token):
    for _ in range(2):
        eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
        client.post(f"/me/events/{eid}/shares", json={"email": "other-lecteur@test.com"}, headers=_h(lecteur_token))
    other = _h(other_lecteur_token)
    first = client.get("/me/notifications", headers=other).json()[0]["id"]
    assert client.post(f"/me/notifications/{first}/read", headers=other).json()["read"] is True
    assert _unread(client, other_lecteur_token) == 1
    assert len(client.get("/me/notifications?unread_only=true", headers=other).json()) == 1
    assert client.post("/me/notifications/read-all", headers=other).json() == {"unread": 0}
    assert _unread(client, other_lecteur_token) == 0


def test_cannot_read_someone_elses_notification(client, lecteur_token, other_lecteur_token):
    eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
    client.post(f"/me/events/{eid}/shares", json={"email": "other-lecteur@test.com"}, headers=_h(lecteur_token))
    nid = client.get("/me/notifications", headers=_h(other_lecteur_token)).json()[0]["id"]
    assert client.post(f"/me/notifications/{nid}/read", headers=_h(lecteur_token)).status_code == 404


def test_deleting_event_removes_its_notifications(client, lecteur_token, other_lecteur_token):
    eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
    client.post(f"/me/events/{eid}/shares", json={"email": "other-lecteur@test.com"}, headers=_h(lecteur_token))
    assert client.delete(f"/me/events/{eid}", headers=_h(lecteur_token)).status_code == 204
    assert client.get("/me/notifications", headers=_h(other_lecteur_token)).json() == []


def _share(client, owner, email="other-lecteur@test.com"):
    eid = client.post("/me/events", json=_payload(), headers=_h(owner)).json()["id"]
    client.post(f"/me/events/{eid}/shares", json={"email": email}, headers=_h(owner))


def test_preferences_default_and_update(client, lecteur_token):
    h = _h(lecteur_token)
    assert client.get("/me/notifications/preferences", headers=h).json() == {
        "notify_in_app": True,
        "notify_email": True,
    }
    r = client.put("/me/notifications/preferences", json={"notify_in_app": False, "notify_email": True}, headers=h)
    assert r.json() == {"notify_in_app": False, "notify_email": True}
    assert client.get("/me/notifications/preferences", headers=h).json()["notify_in_app"] is False


def test_in_app_disabled_still_emails(client, lecteur_token, other_lecteur_token, sent_emails):
    client.put("/me/notifications/preferences", json={"notify_in_app": False, "notify_email": True}, headers=_h(other_lecteur_token))
    _share(client, lecteur_token)
    assert _unread(client, other_lecteur_token) == 0
    assert [m["to"] for m in sent_emails] == ["other-lecteur@test.com"]


def test_email_disabled_still_in_app(client, lecteur_token, other_lecteur_token, sent_emails):
    client.put("/me/notifications/preferences", json={"notify_in_app": True, "notify_email": False}, headers=_h(other_lecteur_token))
    _share(client, lecteur_token)
    assert _unread(client, other_lecteur_token) == 1
    assert sent_emails == []


def test_both_disabled_sends_nothing(client, lecteur_token, other_lecteur_token, sent_emails):
    client.put("/me/notifications/preferences", json={"notify_in_app": False, "notify_email": False}, headers=_h(other_lecteur_token))
    _share(client, lecteur_token)
    assert _unread(client, other_lecteur_token) == 0
    assert sent_emails == []
    # the share itself still works
    assert client.get("/me/events/shared-with-me", headers=_h(other_lecteur_token)).json() != []


def test_admin_preferences_apply_to_moderation_notices(client, lecteur_token, admin_token, sent_emails):
    client.put("/me/notifications/preferences", json={"notify_in_app": False, "notify_email": False}, headers=_h(admin_token))
    client.post("/me/events", json=_payload(visibilite="public"), headers=_h(lecteur_token))
    assert _unread(client, admin_token) == 0
    assert sent_emails == []
