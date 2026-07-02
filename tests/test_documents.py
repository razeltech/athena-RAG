import os

from app.config import settings


def test_upload_list_and_delete_document(client, auth_headers):
    files = {"file": ("sample.txt", b"Athena runs fully offline.", "text/plain")}
    upload = client.post("/v1/documents", headers=auth_headers, files=files)
    assert upload.status_code == 200
    doc_id = upload.json()["doc_id"]

    listed = client.get("/v1/documents", headers=auth_headers)
    assert listed.status_code == 200
    sources = [d["source"] for d in listed.json()]
    assert "sample.txt" in sources

    file_path = os.path.join(settings.upload_dir, "org_default__sample.txt")
    assert os.path.exists(file_path)

    deleted = client.delete(f"/v1/documents/{doc_id}", headers=auth_headers)
    assert deleted.status_code == 200

    listed_after = client.get("/v1/documents", headers=auth_headers)
    assert doc_id not in [d["id"] for d in listed_after.json()]
    assert not os.path.exists(file_path)


def test_delete_unknown_document_returns_404(client, auth_headers):
    resp = client.delete("/v1/documents/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_document_succeeds_even_if_file_removal_fails(client, auth_headers, monkeypatch):
    # Simulates a Windows file-lock (e.g. antivirus/indexer holding the file) —
    # the document should still be removed from retrieval/listing either way.
    files = {"file": ("locked.txt", b"content", "text/plain")}
    upload = client.post("/v1/documents", headers=auth_headers, files=files)
    doc_id = upload.json()["doc_id"]

    monkeypatch.setattr(
        "os.remove",
        lambda path: (_ for _ in ()).throw(PermissionError("file in use")),
    )

    deleted = client.delete(f"/v1/documents/{doc_id}", headers=auth_headers)
    assert deleted.status_code == 200

    listed_after = client.get("/v1/documents", headers=auth_headers)
    assert doc_id not in [d["id"] for d in listed_after.json()]
