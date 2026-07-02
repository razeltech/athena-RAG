from abc import ABC, abstractmethod

from app.core.models import Chunk


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        """Re-score candidate chunks against the query and return the best
        top_k, most-relevant first."""
        ...
