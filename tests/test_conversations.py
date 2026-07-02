from app.api.deps import get_embedder, get_rag_service, get_reranker, get_vectorstore
from app.core.llm import LLMProvider
from app.main import app
from app.services.rag import RagService


class FakeLLM(LLMProvider):
    """Avoids requiring a real running Ollama server for this test — the only
    non-local, non-deterministic piece of the chat flow is faked out."""

    def __init__(self):
        self.received_messages = []

    async def stream_chat(self, messages):
        self.received_messages.append(messages)
        yield "hello"
        yield " world"


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    import json

    events = []
    for part in body.split("\n\n"):
        if not part.strip():
            continue
        event_line, data_line = part.split("\n", 1)
        event = event_line.removeprefix("event: ")
        data = json.loads(data_line.removeprefix("data: "))
        events.append((event, data))
    return events


def _use_fake_llm() -> FakeLLM:
    fake_llm = FakeLLM()
    vectorstore = app.dependency_overrides[get_vectorstore]()
    app.dependency_overrides[get_rag_service] = lambda: RagService(
        get_embedder(), vectorstore, fake_llm, get_reranker()
    )
    return fake_llm


def test_new_conversation_is_persisted_and_replayable(client, auth_headers):
    _use_fake_llm()

    resp = client.post("/v1/chat", headers=auth_headers, json={"message": "Hi there"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    event_types = [e for e, _ in events]
    assert "conversation" in event_types
    assert "done" in event_types

    conversation_id = dict(events)["conversation"]["conversation_id"]

    messages = client.get(
        f"/v1/conversations/{conversation_id}/messages", headers=auth_headers
    ).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Hi there"
    assert messages[1]["content"] == "hello world"

    conversations = client.get("/v1/conversations", headers=auth_headers).json()
    assert conversation_id in [c["id"] for c in conversations]


def test_second_turn_reuses_conversation_and_loads_history(client, auth_headers):
    fake_llm = _use_fake_llm()

    first = client.post("/v1/chat", headers=auth_headers, json={"message": "Hi there"})
    conversation_id = dict(_parse_sse(first.text))["conversation"]["conversation_id"]

    second = client.post(
        "/v1/chat",
        headers=auth_headers,
        json={"message": "follow up", "conversation_id": conversation_id},
    )
    events = _parse_sse(second.text)
    assert "conversation" not in [e for e, _ in events]  # not re-announced

    messages = client.get(
        f"/v1/conversations/{conversation_id}/messages", headers=auth_headers
    ).json()
    assert len(messages) == 4

    # the second call's history (fed to the LLM) should include the first turn
    second_call_history = fake_llm.received_messages[1]
    assert any(m.content == "Hi there" for m in second_call_history)


def test_persona_and_mode_default_and_persist(client, auth_headers):
    _use_fake_llm()
    resp = client.post("/v1/chat", headers=auth_headers, json={"message": "Hi there"})
    conversation_id = dict(_parse_sse(resp.text))["conversation"]["conversation_id"]

    conversations = client.get("/v1/conversations", headers=auth_headers).json()
    conv = next(c for c in conversations if c["id"] == conversation_id)
    assert conv["persona"] == "athena"
    assert conv["mode"] == "answering"


def test_persona_and_mode_can_be_chosen_and_switched(client, auth_headers):
    fake_llm = _use_fake_llm()
    resp = client.post(
        "/v1/chat", headers=auth_headers,
        json={"message": "Hi", "persona": "raza", "mode": "teaching"},
    )
    conversation_id = dict(_parse_sse(resp.text))["conversation"]["conversation_id"]
    assert "Raza" in fake_llm.received_messages[0][0].content
    assert "Mode: Teaching" in fake_llm.received_messages[0][0].content

    client.post(
        "/v1/chat", headers=auth_headers,
        json={"message": "follow up", "conversation_id": conversation_id, "persona": "smiley"},
    )
    assert "Smiley" in fake_llm.received_messages[1][0].content

    conversations = client.get("/v1/conversations", headers=auth_headers).json()
    conv = next(c for c in conversations if c["id"] == conversation_id)
    assert conv["persona"] == "smiley"
    assert conv["mode"] == "teaching"  # unchanged since second call didn't send one


def test_delete_conversation_removes_it(client, auth_headers):
    _use_fake_llm()
    resp = client.post("/v1/chat", headers=auth_headers, json={"message": "Hi there"})
    conversation_id = dict(_parse_sse(resp.text))["conversation"]["conversation_id"]

    deleted = client.delete(f"/v1/conversations/{conversation_id}", headers=auth_headers)
    assert deleted.status_code == 200

    conversations = client.get("/v1/conversations", headers=auth_headers).json()
    assert conversation_id not in [c["id"] for c in conversations]
