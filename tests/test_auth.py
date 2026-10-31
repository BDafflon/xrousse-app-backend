def test_signup_creates_lecteur(client):
    response = client.post("/auth/signup", json={"email": "a@b.com", "password": "secret123"})
    assert response.status_code == 201
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


def test_signup_duplicate_email_rejected(client):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "secret123"})
    response = client.post("/auth/signup", json={"email": "a@b.com", "password": "other456"})
    assert response.status_code == 409


def test_login_wrong_password_rejected(client):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "secret123"})
    response = client.post("/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert response.status_code == 401


def test_login_success(client):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "secret123"})
    response = client.post("/auth/login", json={"email": "a@b.com", "password": "secret123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_refresh_returns_new_access_token(client):
    signup = client.post("/auth/signup", json={"email": "a@b.com", "password": "secret123"})
    refresh_token = signup.json()["refresh_token"]
    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_forgot_password_sends_email_for_known_user(client, monkeypatch):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "secret123"})
    sent = []
    monkeypatch.setattr(
        "app.routers.auth.send_email",
        lambda to, subject, html: sent.append((to, html)),
    )
    response = client.post("/auth/forgot-password", json={"email": "a@b.com"})
    assert response.status_code == 200
    assert len(sent) == 1
    assert sent[0][0] == "a@b.com"
    assert "reset-password?token=" in sent[0][1]


def test_forgot_password_does_not_leak_unknown_email(client, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.routers.auth.send_email",
        lambda to, subject, html: sent.append(to),
    )
    response = client.post("/auth/forgot-password", json={"email": "unknown@b.com"})
    assert response.status_code == 200
    assert sent == []


def test_reset_password_with_valid_token_changes_password(client, monkeypatch):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "secret123"})
    sent = []
    monkeypatch.setattr(
        "app.routers.auth.send_email",
        lambda to, subject, html: sent.append(html),
    )
    client.post("/auth/forgot-password", json={"email": "a@b.com"})
    token = sent[0].split("token=")[1].split('"')[0]

    response = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "newpass456"}
    )
    assert response.status_code == 200

    old_login = client.post("/auth/login", json={"email": "a@b.com", "password": "secret123"})
    assert old_login.status_code == 401
    new_login = client.post("/auth/login", json={"email": "a@b.com", "password": "newpass456"})
    assert new_login.status_code == 200


def test_reset_password_token_single_use(client, monkeypatch):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "secret123"})
    sent = []
    monkeypatch.setattr(
        "app.routers.auth.send_email",
        lambda to, subject, html: sent.append(html),
    )
    client.post("/auth/forgot-password", json={"email": "a@b.com"})
    token = sent[0].split("token=")[1].split('"')[0]

    first = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "newpass456"}
    )
    assert first.status_code == 200

    second = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "anotherpass789"}
    )
    assert second.status_code == 400


def test_reset_password_invalid_token_rejected(client):
    response = client.post(
        "/auth/reset-password", json={"token": "not-a-real-token", "new_password": "newpass456"}
    )
    assert response.status_code == 400
