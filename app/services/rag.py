"""Retrieval-augmented generation. Retrieves org-scoped chunks via hybrid
search (vector + BM25 keyword, fused) and reranking, builds a grounded prompt
that instructs the model to cite with [n], and returns both the prompt
messages and the citation list."""
from app.config import settings
from app.core.embeddings import Embedder
from app.core.llm import LLMProvider
from app.core.models import ChatMessage, Chunk, Citation
from app.core.reranker import Reranker
from app.core.vectorstore import VectorStore
from app.services.hybrid_search import bm25_search, reciprocal_rank_fusion

SYSTEM_PROMPT = (
    "You are a knowledge assistant. Answer the user's question using ONLY the "
    "numbered context passages provided. Cite the passages you use inline with "
    "their number in square brackets, e.g. [1] or [2]. If the answer is not in "
    "the context, say you don't have that information. Be concise and accurate."
)


class RagService:
    def __init__(
        self,
        embedder: Embedder,
        vectorstore: VectorStore,
        llm: LLMProvider,
        reranker: Reranker,
    ):
        self.embedder = embedder
        self.vectorstore = vectorstore
        self.llm = llm
        self.reranker = reranker

    def retrieve(self, org_id: str, question: str) -> list[Chunk]:
        """Hybrid search (vector + BM25, fused) then reranked down to the
        final top-k. Public because scripts/eval.py measures retrieval
        quality independently of the full prepare()+LLM flow."""
        candidate_k = settings.hybrid_candidate_k

        query_emb = self.embedder.embed_query(question)
        vector_results = self.vectorstore.search(org_id, query_emb, candidate_k)

        all_chunks = self.vectorstore.get_all(org_id)
        keyword_results = bm25_search(all_chunks, question, candidate_k)

        fused = reciprocal_rank_fusion(
            [vector_results, keyword_results], top_k=candidate_k
        )
        return self.reranker.rerank(question, fused, settings.retrieval_top_k)

    def _build_context(self, chunks) -> tuple[str, list[Citation]]:
        blocks, citations = [], []
        for i, c in enumerate(chunks, start=1):
            blocks.append(f"[{i}] (source: {c.source})\n{c.text}")
            citations.append(
                Citation(
                    n=i,
                    doc_id=c.doc_id,
                    source=c.source,
                    chunk_index=c.chunk_index,
                    snippet=c.text[:240],
                )
            )
        return "\n\n".join(blocks), citations

    def prepare(
        self, org_id: str, question: str, history: list[ChatMessage] | None = None
    ) -> tuple[list[ChatMessage], list[Citation]]:
        chunks = self.retrieve(org_id, question)
        context, citations = self._build_context(chunks)

        messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        if history:
            messages.extend(history)
        messages.append(
            ChatMessage(
                role="user",
                content=f"Context passages:\n\n{context}\n\nQuestion: {question}",
            )
        )
        return messages, citations
