"""Retrieval-augmented generation. Retrieves org-scoped chunks via hybrid
search (vector + BM25 keyword, fused) and reranking, builds a grounded prompt
from a chosen Persona (tone) + Mode (answer shape), and returns both the
prompt messages and the citation list."""
from datetime import datetime

from app.config import settings
from app.core.embeddings import Embedder
from app.core.llm import LLMProvider
from app.core.models import ChatMessage, Chunk, Citation
from app.core.reranker import Reranker
from app.core.vectorstore import VectorStore
from app.services.hybrid_search import bm25_search, reciprocal_rank_fusion
from app.services.modes import get_mode
from app.services.personas import get_persona

# Applies no matter which persona/mode is active. Grounding/citation is a
# hard rule (see docs D-009 for why abstract style rules need to be paired
# with a concrete worked example to actually stick on a 7B model — personas
# carry their own combined example; this one only needs to cover the parts
# a persona example can't: citation mechanics and the "don't know" case).
BASE_RULES = (
    "Ground every answer ONLY in the numbered context passages you're given. Cite "
    "what you use inline in square brackets, like [1] or [2], right where the "
    "claim is made — not just tacked on at the end. Never write a bracket number "
    "like [1] anywhere in your reply unless passage [1] actually exists in what "
    "you were given — not even to explain that it doesn't exist. A fabricated "
    "citation is worse than no citation: it looks trustworthy but isn't.\n\n"
    "If you are told there are no context passages, or none of them answer the "
    "question, say so plainly in your own voice and stop there. Do not add "
    "anything else — no guesses about the question's subject, no general "
    "knowledge, no assumptions about your own capabilities, and no bracket "
    "numbers. Even something that sounds like a safe, generic fact (e.g. what "
    "file formats might be supported) is a guess if it isn't in front of you — "
    "don't state it.\n"
    "Example (shape only — say it in your own voice, not these exact words):\n"
    "User: what kind of documents do you support?\n"
    "Assistant: I don't have any documents to check right now — nothing's been "
    "uploaded yet for me to look at. Add a document and ask me again.\n\n"
    "One exception to 'only the documents': you are always told the real current "
    "date and time below as a stated fact. You may answer questions about it "
    "directly, with no citation needed — it isn't from a document, it's just what "
    "the server's clock says right now.\n\n"
    "You can only read and discuss documents — you cannot edit, correct, save, or "
    "take any action on a file. When you close with a follow-up, only offer things "
    "you can actually do (answer more, look at another passage, compare against "
    "another document) — never offer to 'fix' or 'update' the document itself."
)


def _style_hint(history: list[ChatMessage] | None) -> str:
    """Loosely mirror the user's own vocabulary/formality — not full
    personalization (no persistent profile, no training), just noticing how
    *this* conversation's user actually talks and reflecting it back."""
    if not history:
        return ""
    user_lines = [m.content for m in history if m.role == "user"][-3:]
    if not user_lines:
        return ""
    sample = "\n".join(f"- {line}" for line in user_lines)
    return (
        "For reference, here's how this user tends to phrase things — loosely "
        "mirror their vocabulary and formality level, don't quote them back "
        f"verbatim:\n{sample}"
    )


def _build_system_prompt(
    persona_id: str | None, mode_id: str | None, history: list[ChatMessage] | None
) -> str:
    persona = get_persona(persona_id)
    mode = get_mode(mode_id)
    now = datetime.now().strftime("%A, %B %d, %Y, %I:%M %p")

    parts = [persona.prompt, mode.prompt, BASE_RULES, _style_hint(history)]
    prompt = "\n\n".join(p for p in parts if p)
    return f"{prompt}\n\nCurrent date and time: {now}."


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
        if not chunks:
            # An empty string here reads to the model as "nothing was
            # provided," not "nothing relevant exists" — it would sometimes
            # fill the gap with general knowledge and a fabricated [1]
            # anyway. An explicit marker removes that ambiguity.
            return (
                "(No documents are available, or none were relevant to this "
                "question — there is nothing to cite.)",
                [],
            )
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
        self,
        org_id: str,
        question: str,
        history: list[ChatMessage] | None = None,
        persona_id: str | None = None,
        mode_id: str | None = None,
    ) -> tuple[list[ChatMessage], list[Citation]]:
        chunks = self.retrieve(org_id, question)
        context, citations = self._build_context(chunks)

        system_prompt = _build_system_prompt(persona_id, mode_id, history)
        messages = [ChatMessage(role="system", content=system_prompt)]
        if history:
            messages.extend(history)
        messages.append(
            ChatMessage(
                role="user",
                content=f"Context passages:\n\n{context}\n\nQuestion: {question}",
            )
        )
        return messages, citations
