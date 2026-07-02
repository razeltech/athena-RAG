"""Retrieval-augmented generation. Retrieves org-scoped chunks, builds a
grounded prompt that instructs the model to cite with [n], and returns both
the prompt messages and the citation list."""
from app.config import settings
from app.core.embeddings import Embedder
from app.core.llm import LLMProvider
from app.core.models import ChatMessage, Citation
from app.core.vectorstore import VectorStore

SYSTEM_PROMPT = (
    "You are a knowledge assistant. Answer the user's question using ONLY the "
    "numbered context passages provided. Cite the passages you use inline with "
    "their number in square brackets, e.g. [1] or [2]. If the answer is not in "
    "the context, say you don't have that information. Be concise and accurate."
)


class RagService:
    def __init__(
        self, embedder: Embedder, vectorstore: VectorStore, llm: LLMProvider
    ):
        self.embedder = embedder
        self.vectorstore = vectorstore
        self.llm = llm

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
        query_emb = self.embedder.embed_query(question)
        chunks = self.vectorstore.search(org_id, query_emb, settings.retrieval_top_k)
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
