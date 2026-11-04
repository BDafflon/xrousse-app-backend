def test_list_tags_includes_seeded(client):
    response = client.get("/tags")
    assert response.status_code == 200
    names = [t["nom"] for t in response.json()]
    assert "Concert" in names


def test_create_tag_requires_auth(client):
    response = client.post("/tags", json={"nom": "Brocante"})
    assert response.status_code == 401


def test_create_tag_as_redacteur(client, redacteur_token):
    response = client.post(
        "/tags",
        json={"nom": "Brocante"},
        headers={"Authorization": f"Bearer {redacteur_token}"},
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "brocante"


def test_create_duplicate_tag_rejected(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    client.post("/tags", json={"nom": "Brocante"}, headers=headers)
    response = client.post("/tags", json={"nom": "Brocante"}, headers=headers)
    assert response.status_code == 409


def test_create_tag_with_famille(client, redacteur_token):
    response = client.post(
        "/tags",
        json={"nom": "Pétanque", "famille": "plein_air"},
        headers={"Authorization": f"Bearer {redacteur_token}"},
    )
    assert response.status_code == 201
    assert response.json()["famille"] == "plein_air"


def test_create_tag_without_famille_defaults_to_autre(client, redacteur_token):
    response = client.post(
        "/tags",
        json={"nom": "Brocante2"},
        headers={"Authorization": f"Bearer {redacteur_token}"},
    )
    assert response.status_code == 201
    assert response.json()["famille"] == "autre"


def test_seeded_tags_have_expected_families(client):
    response = client.get("/tags")
    by_name = {t["nom"]: t["famille"] for t in response.json()}
    assert by_name["Concert"] == "culture"
    assert by_name["Enfants"] == "enfant"
    assert by_name["Solidarité"] == "solidarite"


def test_delete_tag_requires_auth(client):
    response = client.post(
        "/tags", json={"nom": "Vide-greniers"}, headers={}
    )
    assert response.status_code == 401


def test_delete_tag_requires_admin(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post("/tags", json={"nom": "Vide-greniers"}, headers=headers)
    tag_id = created.json()["id"]

    response = client.delete(f"/tags/{tag_id}", headers=headers)
    assert response.status_code == 403


def test_delete_tag_as_admin_hides_it_from_default_list(client, admin_token, redacteur_token):
    created = client.post(
        "/tags",
        json={"nom": "Vide-greniers"},
        headers={"Authorization": f"Bearer {redacteur_token}"},
    )
    tag_id = created.json()["id"]

    response = client.delete(
        f"/tags/{tag_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 204

    names = [t["nom"] for t in client.get("/tags").json()]
    assert "Vide-greniers" not in names

    names_with_deleted = [
        t["nom"] for t in client.get("/tags?include_deleted=true").json()
    ]
    assert "Vide-greniers" in names_with_deleted


def test_restore_tag_as_admin(client, admin_token, redacteur_token):
    created = client.post(
        "/tags",
        json={"nom": "Vide-greniers"},
        headers={"Authorization": f"Bearer {redacteur_token}"},
    )
    tag_id = created.json()["id"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    client.delete(f"/tags/{tag_id}", headers=admin_headers)
    response = client.post(f"/tags/{tag_id}/restore", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["is_deleted"] is False

    names = [t["nom"] for t in client.get("/tags").json()]
    assert "Vide-greniers" in names


def test_restore_tag_requires_admin(client, admin_token, redacteur_token):
    created = client.post(
        "/tags",
        json={"nom": "Vide-greniers"},
        headers={"Authorization": f"Bearer {redacteur_token}"},
    )
    tag_id = created.json()["id"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    client.delete(f"/tags/{tag_id}", headers=admin_headers)
    response = client.post(
        f"/tags/{tag_id}/restore",
        headers={"Authorization": f"Bearer {redacteur_token}"},
    )
    assert response.status_code == 403
