def test_upload_requires_auth(client):
    response = client.post("/backoffice/uploads", files={"file": ("a.png", b"fakepng", "image/png")})
    assert response.status_code == 401


def test_upload_rejects_lecteur(client, lecteur_token):
    response = client.post(
        "/backoffice/uploads",
        files={"file": ("a.png", b"fakepng", "image/png")},
        headers={"Authorization": f"Bearer {lecteur_token}"},
    )
    assert response.status_code == 403


def test_upload_as_redacteur_succeeds(client, redacteur_token, monkeypatch):
    monkeypatch.setattr(
        "app.routers.uploads._require_s3_configured", lambda: None
    )
    monkeypatch.setattr(
        "app.routers.uploads.upload_image", lambda content, content_type: "events/fake.png"
    )
    response = client.post(
        "/backoffice/uploads",
        files={"file": ("a.png", b"fakepng", "image/png")},
        headers={"Authorization": f"Bearer {redacteur_token}"},
    )
    assert response.status_code == 201
    assert response.json() == {"url": "/uploads/events/fake.png"}


def test_upload_rejects_unsupported_type(client, redacteur_token, monkeypatch):
    from app.services.storage import UploadError

    monkeypatch.setattr(
        "app.routers.uploads._require_s3_configured", lambda: None
    )

    def raise_unsupported(content, content_type):
        raise UploadError(f"Unsupported content type: {content_type}")

    monkeypatch.setattr("app.routers.uploads.upload_image", raise_unsupported)
    response = client.post(
        "/backoffice/uploads",
        files={"file": ("a.txt", b"not an image", "text/plain")},
        headers={"Authorization": f"Bearer {redacteur_token}"},
    )
    assert response.status_code == 422


def test_read_upload_proxies_image(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.uploads._require_s3_configured", lambda: None
    )
    monkeypatch.setattr(
        "app.routers.uploads.get_image", lambda key: (b"fake-bytes", "image/png")
    )
    response = client.get("/uploads/events/fake.png")
    assert response.status_code == 200
    assert response.content == b"fake-bytes"
    assert response.headers["content-type"] == "image/png"


def test_read_upload_missing_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.uploads._require_s3_configured", lambda: None
    )

    def raise_not_found(key):
        raise FileNotFoundError(key)

    monkeypatch.setattr("app.routers.uploads.get_image", raise_not_found)
    response = client.get("/uploads/events/missing.png")
    assert response.status_code == 404


def test_upload_returns_503_when_s3_not_configured(client, redacteur_token):
    response = client.post(
        "/backoffice/uploads",
        files={"file": ("a.png", b"fakepng", "image/png")},
        headers={"Authorization": f"Bearer {redacteur_token}"},
    )
    assert response.status_code == 503


def test_upload_with_thumbnail_uses_pair(client, redacteur_token, monkeypatch):
    monkeypatch.setattr("app.routers.uploads._require_s3_configured", lambda: None)
    calls = {}

    def fake_pair(full, full_type, thumb, thumb_type):
        calls["args"] = (full, full_type, thumb, thumb_type)
        return "events/abc_full.jpg"

    monkeypatch.setattr("app.routers.uploads.upload_image_pair", fake_pair)
    response = client.post(
        "/backoffice/uploads",
        files={
            "file": ("a.jpg", b"big", "image/jpeg"),
            "thumbnail": ("t.jpg", b"small", "image/jpeg"),
        },
        headers={"Authorization": f"Bearer {redacteur_token}"},
    )
    assert response.status_code == 201
    assert response.json() == {"url": "/uploads/events/abc_full.jpg"}
    assert calls["args"] == (b"big", "image/jpeg", b"small", "image/jpeg")
