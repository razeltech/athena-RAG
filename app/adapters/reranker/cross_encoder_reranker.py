"""Local cross-encoder reranker. Scores each (query, chunk) pair jointly
(more accurate than comparing two separate embeddings), so it's used only on
the small candidate set hybrid search already narrowed down — too slow to
run over an entire corpus. First run downloads the model once (~80MB) from
HuggingFace via the same sentence-transformers library already used for
embeddings; after that it runs fully offline."""
from app.config import settings
from app.core.models import Chunk
from app.core.reranker import Reranker


class CrossEncoderReranker(Reranker):
    def __init__(self, model_name: str | None = None):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name or settings.reranker_model)

    def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        if not chunks:
            return []
        pairs = [(query, c.text) for c in chunks]
        scores = self.model.predict(pairs)
        ranked = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
        return [chunks[i] for i in ranked[:top_k]]
