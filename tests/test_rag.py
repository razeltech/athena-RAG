from datetime import datetime

from app.core.embeddings import Embedder
from app.core.llm import LLMProvider
from app.core.reranker import Reranker
from app.core.vectorstore import VectorStore
from app.services.rag import RagService, _system_prompt_with_clock


class FakeEmbedder(Embedder):
    def embed_texts(self, texts):
        return [[0.0] for _ in texts]

    def embed_query(self, text):
        return [0.0]


class FakeVectorStore(VectorStore):
    def add(self, chunks, embeddings):
        pass

    def search(self, org_id, query_embedding, top_k):
        return []

    def delete_document(self, org_id, doc_id):
        pass

    def get_all(self, org_id):
        return []


class FakeReranker(Reranker):
    def rerank(self, query, chunks, top_k):
        return chunks[:top_k]


class FakeLLM(LLMProvider):
    async def stream_chat(self, messages):
        yield "ok"


def test_system_prompt_includes_current_year():
    prompt = _system_prompt_with_clock()
    assert str(datetime.now().year) in prompt
    assert "Current date and time:" in prompt


def test_prepare_injects_clock_into_system_message():
    rag = RagService(FakeEmbedder(), FakeVectorStore(), FakeLLM(), FakeReranker())
    messages, citations = rag.prepare("org1", "what time is it?")
    assert messages[0].role == "system"
    assert "Current date and time:" in messages[0].content
    assert citations == []
