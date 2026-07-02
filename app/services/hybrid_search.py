"""Keyword search (BM25) and fusion with vector search results.

Vector search finds passages by *meaning*; BM25 finds them by matching
*words* (great for exact terms — model numbers, names, acronyms — that an
embedding can blur together). Combining both catches more of what a single
method misses. Fusion uses Reciprocal Rank Fusion (RRF): score by rank
position, not raw similarity score, since BM25 scores and cosine similarities
aren't on comparable scales.
"""
import re

from rank_bm25 import BM25Okapi

from app.core.models import Chunk

RRF_K = 60  # standard RRF constant; de-emphasizes the exact top rank a bit
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def bm25_search(chunks: list[Chunk], query: str, top_k: int) -> list[Chunk]:
    """Rank chunks by BM25 keyword relevance to the query."""
    if not chunks:
        return []
    corpus = [_tokenize(c.text) for c in chunks]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    return [chunks[i] for i in ranked[:top_k] if scores[i] > 0]


def reciprocal_rank_fusion(
    rankings: list[list[Chunk]], top_k: int, k: int = RRF_K
) -> list[Chunk]:
    """Merge multiple ranked chunk lists into one, ranked by combined
    reciprocal rank rather than raw scores from different scales."""
    fused_scores: dict[str, float] = {}
    chunk_by_id: dict[str, Chunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking):
            fused_scores[chunk.id] = fused_scores.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)
            chunk_by_id[chunk.id] = chunk

    ordered_ids = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)
    return [chunk_by_id[cid] for cid in ordered_ids[:top_k]]
