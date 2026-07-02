from app.core.models import Chunk
from app.services.hybrid_search import bm25_search, reciprocal_rank_fusion


def _chunk(cid: str, text: str) -> Chunk:
    return Chunk(id=cid, doc_id="doc-1", org_id="org1", source="doc.txt", chunk_index=0, text=text)


def test_bm25_search_ranks_keyword_match_first():
    chunks = [
        _chunk("a", "The quarterly revenue report for widgets"),
        _chunk("b", "A completely unrelated passage about gardening"),
        _chunk("c", "Revenue figures and widget sales this quarter"),
    ]
    results = bm25_search(chunks, "widget revenue", top_k=2)
    assert [c.id for c in results] == ["c", "a"]


def test_bm25_search_excludes_zero_score_matches():
    chunks = [_chunk("a", "apples and oranges")]
    assert bm25_search(chunks, "spaceships", top_k=5) == []


def test_bm25_search_empty_corpus_returns_empty():
    assert bm25_search([], "anything", top_k=5) == []


def test_reciprocal_rank_fusion_combines_rankings():
    a, b, c = _chunk("a", ""), _chunk("b", ""), _chunk("c", "")
    vector_ranking = [a, b, c]
    keyword_ranking = [b, a, c]

    fused = reciprocal_rank_fusion([vector_ranking, keyword_ranking], top_k=3)

    # "a" and "b" are top-2 in both rankings, so they should out-score "c"
    assert {c.id for c in fused[:2]} == {"a", "b"}
    assert fused[2].id == "c"


def test_reciprocal_rank_fusion_dedupes_same_chunk_across_rankings():
    a, b = _chunk("a", ""), _chunk("b", "")
    fused = reciprocal_rank_fusion([[a, b], [a]], top_k=5)
    assert len(fused) == 2
    assert fused[0].id == "a"  # appears in both rankings, ranks first in both
