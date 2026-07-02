"""Word-based chunker with overlap. Simple and dependency-free for Phase 1.
TODO: swap to a token-based splitter so chunk sizes align with the model's
context window more precisely."""
from app.config import settings


def chunk_text(
    text: str, chunk_size: int | None = None, overlap: int | None = None
) -> list[str]:
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    words = text.split()
    if not words:
        return []
    step = max(1, chunk_size - overlap)
    chunks: list[str] = []
    for start in range(0, len(words), step):
        piece = " ".join(words[start : start + chunk_size]).strip()
        if piece:
            chunks.append(piece)
        if start + chunk_size >= len(words):
            break
    return chunks
