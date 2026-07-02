"""parse -> chunk -> embed -> store -> record. Every chunk is tagged with
org_id so retrieval stays tenant-isolated."""
import uuid

from app.adapters.parsers.registry import ParserRegistry
from app.core.embeddings import Embedder
from app.core.models import Chunk
from app.core.vectorstore import VectorStore
from app.db.database import SessionLocal
from app.db.models import Document
from app.services.chunking import chunk_text


class IngestService:
    def __init__(
        self,
        embedder: Embedder,
        vectorstore: VectorStore,
        registry: ParserRegistry | None = None,
    ):
        self.embedder = embedder
        self.vectorstore = vectorstore
        self.registry = registry or ParserRegistry()

    async def ingest_file(self, path: str, source: str, org_id: str) -> dict:
        parsed = self.registry.parse(path, source)
        texts = chunk_text(parsed.text)
        if not texts:
            raise ValueError("No text could be extracted from the document.")

        doc_id = str(uuid.uuid4())
        chunks = [
            Chunk(
                id=f"{doc_id}:{i}",
                doc_id=doc_id,
                org_id=org_id,
                source=source,
                chunk_index=i,
                text=t,
            )
            for i, t in enumerate(texts)
        ]
        embeddings = self.embedder.embed_texts([c.text for c in chunks])
        self.vectorstore.add(chunks, embeddings)

        async with SessionLocal() as session:
            session.add(
                Document(id=doc_id, org_id=org_id, source=source, chunk_count=len(chunks))
            )
            await session.commit()

        return {"doc_id": doc_id, "source": source, "chunks": len(chunks)}
