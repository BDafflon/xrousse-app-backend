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
