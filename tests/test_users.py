def test_admin_can_create_redacteur(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.post("/backoffice/users", json={"email": "r@b.com", "password": "secret123", "role": "redacteur"}, headers=headers)
    assert response.status_code == 201
    assert response.json()["role"] == "redacteur"


def test_redacteur_cannot_create_users(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    response = client.post("/backoffice/users", json={"email": "r2@b.com", "password": "secret123", "role": "redacteur"}, headers=headers)
    assert response.status_code == 403


def test_cannot_delete_last_admin(client, admin_token, admin_user_id):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.delete(f"/backoffice/users/{admin_user_id}", headers=headers)
    assert response.status_code == 400


def test_create_user_conflict_on_existing_email(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    client.post("/backoffice/users", json={"email": "dup@b.com", "password": "secret123", "role": "redacteur"}, headers=headers)
    response = client.post("/backoffice/users", json={"email": "dup@b.com", "password": "secret123", "role": "redacteur"}, headers=headers)
    assert response.status_code == 409


def test_list_users_as_admin(client, admin_token, admin_user_id):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/backoffice/users", headers=headers)
    assert response.status_code == 200
    emails = [u["email"] for u in response.json()]
    assert "admin@test.com" in emails


def test_list_users_rejects_lecteur(client, lecteur_token):
    headers = {"Authorization": f"Bearer {lecteur_token}"}
    response = client.get("/backoffice/users", headers=headers)
    assert response.status_code == 403


def test_delete_user_not_found(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.delete("/backoffice/users/999999", headers=headers)
    assert response.status_code == 404


def test_delete_user_succeeds_when_not_last_admin(client, admin_token, admin_user_id):
    headers = {"Authorization": f"Bearer {admin_token}"}
    created = client.post("/backoffice/users", json={"email": "r3@b.com", "password": "secret123", "role": "redacteur"}, headers=headers)
    user_id = created.json()["id"]
    response = client.delete(f"/backoffice/users/{user_id}", headers=headers)
    assert response.status_code == 204


def test_delete_admin_succeeds_when_another_admin_exists(client, admin_token, admin_user_id):
    headers = {"Authorization": f"Bearer {admin_token}"}
    created = client.post("/backoffice/users", json={"email": "admin2@b.com", "password": "secret123", "role": "admin"}, headers=headers)
    second_admin_id = created.json()["id"]
    response = client.delete(f"/backoffice/users/{second_admin_id}", headers=headers)
    assert response.status_code == 204


def test_delete_user_with_created_event_returns_409(client, admin_token, redacteur_token):
    # Regression for I1: deleting a user who authored an event must not 500
    # in Postgres (event.created_by_id has no ON DELETE rule); blocked with
    # a clear 409 instead of silently cascading away authored content.
    import jwt as pyjwt

    from app.config import get_settings

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    payload = pyjwt.decode(
        redacteur_token, get_settings().jwt_secret_key, algorithms=["HS256"]
    )
    redacteur_id = int(payload["sub"])

    redacteur_headers = {"Authorization": f"Bearer {redacteur_token}"}
    client.post(
        "/backoffice/events",
        json={"source_url": "https://example.com/userdel1"},
        headers=redacteur_headers,
    )

    response = client.delete(f"/backoffice/users/{redacteur_id}", headers=admin_headers)
    assert response.status_code == 409
    assert "created events" in response.json()["detail"]
