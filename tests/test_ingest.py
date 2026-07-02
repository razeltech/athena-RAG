import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.vectorstore.chroma_store import ChromaVectorStore
from app.core.embeddings import Embedder
from app.db.models import Base, Document
from app.services.ingest import IngestService


class FakeEmbedder(Embedder):
    """Fixed-length dummy vectors — avoids loading the real, heavy
    sentence-transformers model in what should be a fast unit test."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


@pytest.mark.asyncio
async def test_ingest_file_persists_document_row(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.services.ingest.SessionLocal", session_factory)

    store = ChromaVectorStore(persist_dir=str(tmp_path / "chroma"))
    service = IngestService(FakeEmbedder(), store)

    sample = tmp_path / "sample.txt"
    sample.write_text("Athena runs fully offline using Ollama and Chroma.")

    result = await service.ingest_file(str(sample), "sample.txt", "org_default")

    assert result["source"] == "sample.txt"
    assert result["chunks"] == 1

    async with session_factory() as session:
        doc = await session.get(Document, result["doc_id"])
        assert doc is not None
        assert doc.org_id == "org_default"
        assert doc.source == "sample.txt"
        assert doc.chunk_count == 1

    await engine.dispose()
