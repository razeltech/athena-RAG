from app.adapters.reranker.cross_encoder_reranker import CrossEncoderReranker
from app.core.models import Chunk


def _chunk(cid: str, text: str) -> Chunk:
    return Chunk(id=cid, doc_id="doc-1", org_id="org1", source="doc.txt", chunk_index=0, text=text)


def test_reranker_prefers_more_relevant_chunk():
    reranker = CrossEncoderReranker()
    chunks = [
        _chunk("irrelevant", "Bananas are a good source of potassium."),
        _chunk("relevant", "The capital of France is Paris."),
    ]

    ranked = reranker.rerank("What is the capital of France?", chunks, top_k=2)

    assert ranked[0].id == "relevant"


def test_reranker_respects_top_k():
    reranker = CrossEncoderReranker()
    chunks = [_chunk(str(i), f"passage number {i}") for i in range(5)]

    ranked = reranker.rerank("passage", chunks, top_k=2)

    assert len(ranked) == 2


def test_reranker_empty_chunks_returns_empty():
    reranker = CrossEncoderReranker()
    assert reranker.rerank("anything", [], top_k=5) == []
