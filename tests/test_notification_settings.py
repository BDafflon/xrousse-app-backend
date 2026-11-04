from sqlmodel import select

from app.models.tag import Tag


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _prefs(client, token, **body):
    r = client.put("/me/notifications/preferences", json=body, headers=_h(token))
    assert r.status_code == 200, r.text
    return r.json()


def _unread(client, token):
    return client.get("/me/notifications/unread-count", headers=_h(token)).json()["unread"]


def _publish(client, redacteur_token, tag_ids=(), **kw):
    h = _h(redacteur_token)
    n = len(client.get("/backoffice/events", headers=h).json())
    eid = client.post("/backoffice/events", json={
        "source_url": f"https://example.com/n{n}", "titre": "Vide grenier", "date": "2026-11-15T10:00:00",
        "tag_ids": list(tag_ids), **kw,
    }, headers=h).json()["id"]
    assert client.post(f"/backoffice/events/{eid}/publish", headers=h).status_code == 200
    return eid


def test_partial_update_keeps_other_fields(client, lecteur_token):
    _prefs(client, lecteur_token, notify_new_events=True)
    p = _prefs(client, lecteur_token, notify_email=False)
    assert p["notify_new_events"] is True and p["notify_email"] is False and p["notify_in_app"] is True


def test_new_events_off_by_default(client, lecteur_token, redacteur_token):
    _publish(client, redacteur_token)
    assert _unread(client, lecteur_token) == 0


def test_new_event_notifies_opted_in_users_for_all_tags(client, lecteur_token, redacteur_token, sent_emails, sent_pushes):
    _prefs(client, lecteur_token, notify_new_events=True)
    eid = _publish(client, redacteur_token)
    n = client.get("/me/notifications", headers=_h(lecteur_token)).json()
    assert [(x["type"], x["link"]) for x in n] == [("event_published", f"/events/{eid}")]
    assert [m["to"] for m in sent_emails] == ["lecteur@test.com"]
    assert len(sent_pushes) == 1


def test_author_is_not_notified_of_own_event(client, redacteur_token):
    _prefs(client, redacteur_token, notify_new_events=True)
    _publish(client, redacteur_token)
    assert _unread(client, redacteur_token) == 0


def test_tag_filter(client, session, lecteur_token, other_lecteur_token, redacteur_token):
    tags = session.exec(select(Tag)).all()
    a, b = tags[0].id, tags[1].id
    _prefs(client, lecteur_token, notify_new_events=True, new_event_tag_ids=[a])
    _prefs(client, other_lecteur_token, notify_new_events=True)  # all tags

    _publish(client, redacteur_token, tag_ids=[b])
    assert _unread(client, lecteur_token) == 0       # not interested in tag b
    assert _unread(client, other_lecteur_token) == 1

    _publish(client, redacteur_token, tag_ids=[a, b])
    assert _unread(client, lecteur_token) == 1       # matches tag a
    _publish(client, redacteur_token)                # no tag at all
    assert _unread(client, lecteur_token) == 1       # filtered users skip untagged events
    assert _unread(client, other_lecteur_token) == 3


def test_tag_filter_roundtrip_replace_and_clear(client, session, lecteur_token):
    a, b = [t.id for t in session.exec(select(Tag)).all()[:2]]
    assert _prefs(client, lecteur_token, new_event_tag_ids=[b, a])["new_event_tag_ids"] == sorted([a, b])
    assert _prefs(client, lecteur_token, new_event_tag_ids=[a])["new_event_tag_ids"] == [a]
    assert _prefs(client, lecteur_token, notify_event_shared=False)["new_event_tag_ids"] == [a]  # untouched
    assert _prefs(client, lecteur_token, new_event_tag_ids=[])["new_event_tag_ids"] == []


def test_unknown_tag_rejected(client, lecteur_token):
    r = client.put("/me/notifications/preferences", json={"new_event_tag_ids": [999999]}, headers=_h(lecteur_token))
    assert r.status_code == 422


def test_moderation_approval_also_notifies_followers(client, lecteur_token, other_lecteur_token, admin_token):
    _prefs(client, other_lecteur_token, notify_new_events=True)
    eid = client.post("/me/events", json={"titre": "Fête", "date": "2026-12-01T10:00:00", "visibilite": "public"}, headers=_h(lecteur_token)).json()["id"]
    client.post(f"/backoffice/moderation/events/{eid}/approve", headers=_h(admin_token))
    types = [n["type"] for n in client.get("/me/notifications", headers=_h(other_lecteur_token)).json()]
    assert types == ["event_published"]


def test_private_event_never_announced(client, lecteur_token, other_lecteur_token):
    _prefs(client, other_lecteur_token, notify_new_events=True)
    client.post("/me/events", json={"titre": "Perso", "date": "2026-12-01T10:00:00"}, headers=_h(lecteur_token))
    assert _unread(client, other_lecteur_token) == 0


def test_no_double_email_for_tag_subscribers(client, session, lecteur_token, redacteur_token, sent_emails, monkeypatch):
    from app.models.subscription import AlertMode, Subscription
    from app.models.user import User

    tag = session.exec(select(Tag)).first()
    user = session.exec(select(User).where(User.email == "lecteur@test.com")).one()
    session.add(Subscription(user_id=user.id, tag_id=tag.id, mode=AlertMode.immediat))
    session.commit()
    alert_mails = []
    monkeypatch.setattr("app.services.alerts.send_email", lambda to, subject, html: alert_mails.append(to))
    _prefs(client, lecteur_token, notify_new_events=True)
    _publish(client, redacteur_token, tag_ids=[tag.id])
    assert alert_mails == ["lecteur@test.com"]       # subscription email
    assert sent_emails == []                         # no second email...
    assert _unread(client, lecteur_token) == 1       # ...but the in-app one is there


def test_shared_with_me_can_be_switched_off(client, lecteur_token, other_lecteur_token, sent_emails, sent_pushes):
    _prefs(client, other_lecteur_token, notify_event_shared=False)
    eid = client.post("/me/events", json={"titre": "Perso"}, headers=_h(lecteur_token)).json()["id"]
    r = client.post(f"/me/events/{eid}/shares", json={"email": "other-lecteur@test.com"}, headers=_h(lecteur_token))
    assert r.status_code == 201
    assert _unread(client, other_lecteur_token) == 0 and sent_emails == [] and sent_pushes == []
    # the event is still shared, only the notification is muted
    assert client.get("/me/events/shared-with-me", headers=_h(other_lecteur_token)).json() != []


def test_deleting_user_removes_tag_filters(client, session, lecteur_token, admin_token):
    from app.models.user import User

    t = session.exec(select(Tag)).first().id
    _prefs(client, lecteur_token, new_event_tag_ids=[t])
    uid = session.exec(select(User).where(User.email == "lecteur@test.com")).one().id
    assert client.delete(f"/backoffice/users/{uid}", headers=_h(admin_token)).status_code == 204
