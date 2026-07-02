from abc import ABC, abstractmethod

from app.core.models import Chunk


class VectorStore(ABC):
    @abstractmethod
    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        ...

    @abstractmethod
    def search(
        self, org_id: str, query_embedding: list[float], top_k: int
    ) -> list[Chunk]:
        """Return the top_k most similar chunks, filtered to one org."""
        ...

    @abstractmethod
    def delete_document(self, org_id: str, doc_id: str) -> None:
        """Remove every chunk belonging to one document, scoped to one org."""
        ...
