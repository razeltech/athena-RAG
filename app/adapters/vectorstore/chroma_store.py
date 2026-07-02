"""Local Chroma vector store. Persistent on disk, supports metadata filtering
so every query is scoped by org_id. To swap to Qdrant, add a sibling adapter
implementing VectorStore — nothing else changes."""
import chromadb

from app.config import settings
from app.core.models import Chunk
from app.core.vectorstore import VectorStore


class ChromaVectorStore(VectorStore):
    def __init__(self, persist_dir: str | None = None):
        self.client = chromadb.PersistentClient(path=persist_dir or settings.chroma_dir)
        self.collection = self.client.get_or_create_collection(
            name="chunks", metadata={"hnsw:space": "cosine"}
        )

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        self.collection.add(
            ids=[c.id for c in chunks],
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "doc_id": c.doc_id,
                    "org_id": c.org_id,
                    "source": c.source,
                    "chunk_index": c.chunk_index,
                }
                for c in chunks
            ],
        )

    def search(
        self, org_id: str, query_embedding: list[float], top_k: int
    ) -> list[Chunk]:
        res = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"org_id": org_id},  # tenant isolation enforced here
        )
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        chunks: list[Chunk] = []
        for cid, text, meta in zip(ids, docs, metas):
            chunks.append(
                Chunk(
                    id=cid,
                    doc_id=meta["doc_id"],
                    org_id=meta["org_id"],
                    source=meta["source"],
                    chunk_index=int(meta["chunk_index"]),
                    text=text,
                )
            )
        return chunks

    def delete_document(self, org_id: str, doc_id: str) -> None:
        # chromadb requires exactly one top-level where operator, so a
        # multi-key filter needs an explicit $and.
        self.collection.delete(
            where={"$and": [{"org_id": org_id}, {"doc_id": doc_id}]}
        )

    def get_all(self, org_id: str) -> list[Chunk]:
        res = self.collection.get(where={"org_id": org_id})
        ids = res.get("ids") or []
        docs = res.get("documents") or []
        metas = res.get("metadatas") or []
        return [
            Chunk(
                id=cid,
                doc_id=meta["doc_id"],
                org_id=meta["org_id"],
                source=meta["source"],
                chunk_index=int(meta["chunk_index"]),
                text=text,
            )
            for cid, text, meta in zip(ids, docs, metas)
        ]
