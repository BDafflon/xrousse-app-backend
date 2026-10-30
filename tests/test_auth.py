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
