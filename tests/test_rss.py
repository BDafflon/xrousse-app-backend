import xml.etree.ElementTree as ET


def test_rss_feed_contains_published_event(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    created = client.post("/backoffice/events", json={
        "source_url": "https://example.com/g1", "titre": "Marché de Noël", "date": "2026-12-01T09:00:00"
    }, headers=headers)
    event_id = created.json()["id"]
    client.post(f"/backoffice/events/{event_id}/publish", headers=headers)
    response = client.get("/rss.xml")
    assert response.status_code == 200
    assert "Marché de Noël" in response.text
    assert response.headers["content-type"].startswith("application/rss+xml")


def test_rss_feed_excludes_drafts(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    client.post("/backoffice/events", json={"source_url": "https://example.com/g2"}, headers=headers)
    response = client.get("/rss.xml")
    assert "https://example.com/g2" not in response.text


def test_rss_feed_is_valid_rss2_with_item_fields_and_date_desc_order(client, redacteur_token):
    headers = {"Authorization": f"Bearer {redacteur_token}"}
    events = [
        {"source_url": "https://example.com/g3", "titre": "Ancien", "description": "Desc A",
         "date": "2026-11-01T10:00:00"},
        {"source_url": "https://example.com/g4", "titre": "Récent", "description": "Desc B",
         "date": "2026-12-15T18:30:00"},
    ]
    for payload in events:
        created = client.post("/backoffice/events", json=payload, headers=headers)
        client.post(f"/backoffice/events/{created.json()['id']}/publish", headers=headers)

    response = client.get("/rss.xml")
    root = ET.fromstring(response.content)

    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    items = root.findall("./channel/item")
    assert [item.findtext("title") for item in items] == ["Récent", "Ancien"]
    first = items[0]
    assert first.findtext("description") == "Desc B"
    assert first.findtext("link") == "https://example.com/g4"
    # Naive event dates are local Lyon time (Europe/Paris, CET = UTC+1 in December).
    assert first.findtext("pubDate") == "Tue, 15 Dec 2026 17:30:00 +0000"
