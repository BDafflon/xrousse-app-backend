def test_create_immediate_subscription(client, lecteur_token, tag_id):
    headers = {"Authorization": f"Bearer {lecteur_token}"}
    response = client.post(
        "/subscriptions", json={"tag_id": tag_id, "mode": "immediat"}, headers=headers
    )
    assert response.status_code == 201


def test_resume_subscription_requires_day(client, lecteur_token, tag_id):
    headers = {"Authorization": f"Bearer {lecteur_token}"}
    response = client.post(
        "/subscriptions", json={"tag_id": tag_id, "mode": "resume"}, headers=headers
    )
    assert response.status_code == 422


def test_resume_subscription_with_day_succeeds(client, lecteur_token, tag_id):
    headers = {"Authorization": f"Bearer {lecteur_token}"}
    response = client.post(
        "/subscriptions",
        json={"tag_id": tag_id, "mode": "resume", "resume_day": 0},
        headers=headers,
    )
    assert response.status_code == 201


def test_duplicate_subscription_rejected(client, lecteur_token, tag_id):
    headers = {"Authorization": f"Bearer {lecteur_token}"}
    client.post(
        "/subscriptions", json={"tag_id": tag_id, "mode": "immediat"}, headers=headers
    )
    response = client.post(
        "/subscriptions", json={"tag_id": tag_id, "mode": "immediat"}, headers=headers
    )
    assert response.status_code == 409


def test_delete_subscription_not_owned_404(
    client, lecteur_token, other_lecteur_token, tag_id
):
    headers = {"Authorization": f"Bearer {lecteur_token}"}
    sub = client.post(
        "/subscriptions", json={"tag_id": tag_id, "mode": "immediat"}, headers=headers
    ).json()
    other_headers = {"Authorization": f"Bearer {other_lecteur_token}"}
    response = client.delete(f"/subscriptions/{sub['id']}", headers=other_headers)
    assert response.status_code == 404


def test_delete_subscription_owned_succeeds(client, lecteur_token, tag_id):
    headers = {"Authorization": f"Bearer {lecteur_token}"}
    sub = client.post(
        "/subscriptions", json={"tag_id": tag_id, "mode": "immediat"}, headers=headers
    ).json()
    response = client.delete(f"/subscriptions/{sub['id']}", headers=headers)
    assert response.status_code == 204


def test_list_subscriptions_returns_only_own(
    client, lecteur_token, other_lecteur_token, tag_id
):
    headers = {"Authorization": f"Bearer {lecteur_token}"}
    client.post(
        "/subscriptions", json={"tag_id": tag_id, "mode": "immediat"}, headers=headers
    )
    other_headers = {"Authorization": f"Bearer {other_lecteur_token}"}
    response = client.get("/subscriptions", headers=other_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_subscriptions_require_authentication(client, tag_id):
    response = client.post(
        "/subscriptions", json={"tag_id": tag_id, "mode": "immediat"}
    )
    assert response.status_code == 401
