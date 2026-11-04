from sqlmodel import select

from app.models.push_token import PushToken
from app.services import push as push_service

TOKEN = "t" * 40


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _payload(**kw):
    return {"titre": "Ma sortie", "date": "2026-12-01T10:00:00", **kw}


def test_register_requires_auth(client):
    assert client.put("/me/push-tokens", json={"token": TOKEN, "platform": "web"}).status_code == 401


def test_register_is_idempotent_and_validates(client, session, lecteur_token):
    h = _h(lecteur_token)
    for _ in range(2):
        assert client.put("/me/push-tokens", json={"token": TOKEN, "platform": "web"}, headers=h).status_code == 204
    assert len(session.exec(select(PushToken)).all()) == 1
    assert client.put("/me/push-tokens", json={"token": TOKEN, "platform": "toaster"}, headers=h).status_code == 422
    assert client.put("/me/push-tokens", json={"token": "x", "platform": "web"}, headers=h).status_code == 422


def test_token_moves_to_new_user_on_shared_device(client, session, lecteur_token, other_lecteur_token):
    client.put("/me/push-tokens", json={"token": TOKEN, "platform": "web"}, headers=_h(lecteur_token))
    client.put("/me/push-tokens", json={"token": TOKEN, "platform": "web"}, headers=_h(other_lecteur_token))
    tokens = session.exec(select(PushToken)).all()
    from app.models.user import User

    other = session.exec(select(User).where(User.email == "other-lecteur@test.com")).one()
    assert len(tokens) == 1 and tokens[0].user_id == other.id
    # the previous user can no longer unregister (nor affect) it
    client.post("/me/push-tokens/unregister", json={"token": TOKEN, "platform": "web"}, headers=_h(lecteur_token))
    assert len(session.exec(select(PushToken)).all()) == 1


def test_unregister(client, session, lecteur_token):
    h = _h(lecteur_token)
    client.put("/me/push-tokens", json={"token": TOKEN, "platform": "android"}, headers=h)
    assert client.post("/me/push-tokens/unregister", json={"token": TOKEN, "platform": "android"}, headers=h).status_code == 204
    assert session.exec(select(PushToken)).all() == []
    assert client.post("/me/push-tokens/unregister", json={"token": TOKEN, "platform": "android"}, headers=h).status_code == 204


def test_notification_triggers_push(client, lecteur_token, other_lecteur_token, sent_pushes):
    client.put("/me/push-tokens", json={"token": TOKEN, "platform": "web"}, headers=_h(other_lecteur_token))
    eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
    client.post(f"/me/events/{eid}/shares", json={"email": "other-lecteur@test.com"}, headers=_h(lecteur_token))
    assert len(sent_pushes) == 1
    assert sent_pushes[0]["link"] == "/my-events/created"


def test_no_push_when_in_app_notifications_disabled(client, lecteur_token, other_lecteur_token, sent_pushes):
    client.put("/me/notifications/preferences", json={"notify_in_app": False, "notify_email": True}, headers=_h(other_lecteur_token))
    eid = client.post("/me/events", json=_payload(), headers=_h(lecteur_token)).json()["id"]
    client.post(f"/me/events/{eid}/shares", json={"email": "other-lecteur@test.com"}, headers=_h(lecteur_token))
    assert sent_pushes == []


def test_send_push_noop_without_firebase_credentials(session, lecteur_token):
    from app.models.user import User

    push_service._firebase_app.cache_clear()
    user = session.exec(select(User)).first()
    # must not raise even though no credentials are configured
    push_service.send_push(session, user, "t", "b", "/")


def test_dead_tokens_are_pruned(session, lecteur_token, monkeypatch):
    from firebase_admin import messaging

    from app.models.user import User

    user = session.exec(select(User)).first()
    session.add(PushToken(user_id=user.id, token=TOKEN, platform="web"))
    session.commit()
    monkeypatch.setattr(push_service, "_firebase_app", lambda: object())

    def boom(*a, **k):
        raise messaging.UnregisteredError("gone", None, None)

    monkeypatch.setattr(messaging, "send", boom)
    push_service.send_push(session, user, "t", "b", "/")
    assert session.exec(select(PushToken)).all() == []
