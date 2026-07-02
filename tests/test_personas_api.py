def test_list_personas_endpoint(client, auth_headers):
    resp = client.get("/v1/personas", headers=auth_headers)
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert {"athena", "meera", "smiley", "raza"} <= ids


def test_list_modes_endpoint(client, auth_headers):
    resp = client.get("/v1/modes", headers=auth_headers)
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()}
    assert {"answering", "explaining", "teaching", "review", "summary"} <= ids
