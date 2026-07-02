from app.adapters.vectorstore.chroma_store import ChromaVectorStore
from app.core.models import Chunk


def _chunk(doc_id: str, org_id: str, index: int, text: str) -> Chunk:
    # In production doc_id is always a fresh uuid4, so ids never collide across
    # orgs; include org_id here purely so this test's fixture ids stay unique.
    return Chunk(
        id=f"{org_id}:{doc_id}:{index}",
        doc_id=doc_id,
        org_id=org_id,
        source=f"{doc_id}.txt",
        chunk_index=index,
        text=text,
    )


def test_delete_document_removes_only_its_own_chunks(tmp_path):
    store = ChromaVectorStore(persist_dir=str(tmp_path / "chroma"))

    chunk_a = _chunk("doc-a", "org1", 0, "alpha")
    chunk_b = _chunk("doc-b", "org1", 0, "beta")
    store.add([chunk_a, chunk_b], embeddings=[[1.0, 0.0], [0.0, 1.0]])

    store.delete_document("org1", "doc-a")

    remaining = store.search("org1", query_embedding=[1.0, 0.0], top_k=10)
    assert [c.doc_id for c in remaining] == ["doc-b"]


def test_delete_document_is_scoped_to_org(tmp_path):
    store = ChromaVectorStore(persist_dir=str(tmp_path / "chroma"))

    chunk_org1 = _chunk("doc-shared", "org1", 0, "alpha")
    chunk_org2 = _chunk("doc-shared", "org2", 0, "alpha")
    store.add([chunk_org1, chunk_org2], embeddings=[[1.0, 0.0], [1.0, 0.0]])

    store.delete_document("org1", "doc-shared")

    assert store.search("org1", query_embedding=[1.0, 0.0], top_k=10) == []
    assert len(store.search("org2", query_embedding=[1.0, 0.0], top_k=10)) == 1


def test_get_all_returns_every_chunk_for_one_org(tmp_path):
    store = ChromaVectorStore(persist_dir=str(tmp_path / "chroma"))

    chunk_a = _chunk("doc-a", "org1", 0, "alpha")
    chunk_b = _chunk("doc-b", "org1", 0, "beta")
    chunk_other_org = _chunk("doc-c", "org2", 0, "gamma")
    store.add(
        [chunk_a, chunk_b, chunk_other_org],
        embeddings=[[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
    )

    all_org1 = store.get_all("org1")
    assert {c.doc_id for c in all_org1} == {"doc-a", "doc-b"}

    all_org2 = store.get_all("org2")
    assert [c.doc_id for c in all_org2] == ["doc-c"]
