import pytest


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="event_id")
def event_id_fixture(client, redacteur_token):
    headers = _auth(redacteur_token)
    created = client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/rep1", "titre": "Fete", "date": "2099-11-20T10:00:00"},
        headers=headers,
    )
    event_id = created.json()["id"]
    client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    return event_id


def test_report_requires_auth(client, event_id):
    assert client.post(f"/events/{event_id}/reports", json={"reason": "spam"}).status_code == 401


def test_report_rejects_unknown_reason(client, lecteur_token, event_id):
    r = client.post(f"/events/{event_id}/reports", json={"reason": "nope"}, headers=_auth(lecteur_token))
    assert r.status_code == 422


def test_report_unknown_event(client, lecteur_token):
    r = client.post("/events/9999/reports", json={"reason": "spam"}, headers=_auth(lecteur_token))
    assert r.status_code == 404


def test_report_then_not_visible_to_non_admin(client, lecteur_token, event_id):
    r = client.post(f"/events/{event_id}/reports", json={"reason": "illegal"}, headers=_auth(lecteur_token))
    assert r.status_code == 204
    assert client.get("/backoffice/moderation/reports", headers=_auth(lecteur_token)).status_code == 403


def test_report_is_idempotent_and_admin_can_resolve(client, session, lecteur_token, event_id):
    from app.auth.security import create_access_token
    from app.models.user import Role, User

    headers = _auth(lecteur_token)
    client.post(f"/events/{event_id}/reports", json={"reason": "spam"}, headers=headers)
    client.post(f"/events/{event_id}/reports", json={"reason": "illegal"}, headers=headers)

    admin = User(email="admin@test.com", password_hash="x", role=Role.admin)
    session.add(admin)
    session.commit()
    session.refresh(admin)
    admin_headers = _auth(create_access_token(admin))

    listed = client.get("/backoffice/moderation/reports", headers=admin_headers).json()
    assert len(listed) == 1
    assert listed[0]["reason"] == "spam"
    assert listed[0]["event_titre"] == "Fete"

    assert client.post(f"/backoffice/moderation/reports/{listed[0]['id']}/resolve", headers=admin_headers).status_code == 204
    assert client.get("/backoffice/moderation/reports", headers=admin_headers).json() == []
    assert len(client.get("/backoffice/moderation/reports?resolved=true", headers=admin_headers).json()) == 1
