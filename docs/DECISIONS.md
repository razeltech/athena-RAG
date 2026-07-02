# Decision Log

Every important choice gets an entry so that in six months — or when a second developer joins — you know *why*, not just *what*. Newest at the top.

**Format:** each entry has Context · Options · Decision · Consequences · Status (`accepted` / `open` / `superseded`).

---

## D-007 — `/v1/chat` becomes conversation-scoped, dropping client-resent `history` · Status: accepted

- **Context:** Chat history was entirely client-side (the browser resent the full message array every turn, lost on refresh/restart). The user wanted ChatGPT/Claude-style persistent, resumable conversations with a sidebar.
- **Decision:** Added `Conversation`/`Message` tables (`app/db/models.py`). `ChatRequest` drops `history: list[ChatMessage]` and gains `conversation_id: str | None`. The server loads prior turns from the DB, persists both the user and assistant turns, and a new `conversation` SSE event (emitted once, only for a newly-created conversation) returns the new id to the client.
- **Consequences:** This is a breaking change to `/v1/chat`'s request contract — acceptable because it's made *before* any external client (Unity/Quest) depends on it; the API-stability rule in `rules.md` exists to protect that future client, not to freeze the contract pre-emptively. Citations are stored as a JSON column on `Message` rather than a separate table (simplest fit for SQLite, revisit only if citations need independent querying). Known gap: `Document`/`Conversation` reference `organizations.id` by FK, but no real org-provisioning flow exists yet — a single `"org_default"` row is upserted at startup so the FK stays meaningful (matters once/if a real Postgres deployment enforces FKs). Separate known gap, surfaced (not fixed) while adding document delete: the upload route reconstructs an on-disk filename as `{org_id}__{filename}`, so two uploads with the same filename silently overwrite each other's file — a real fix would add a `Document.stored_filename` column, bigger than this round's scope.

---

## D-006 — Automatic DB table + default-org creation on startup · Status: accepted

- **Context:** `scripts/init_db.py` was a manual, "optional" step. Once document persistence and chat history depend on tables existing, skipping it silently breaks those features instead of failing loudly at setup time.
- **Decision:** `app/main.py`'s FastAPI `lifespan` now runs `Base.metadata.create_all` and upserts a single default `Organization` row on startup. `scripts/init_db.py` still exists for manual/CI use (e.g. pre-provisioning a real Postgres DB before first boot).
- **Consequences:** One less manual step for local dev; no behavior change for a fresh Postgres setup that still wants to run the script ahead of time (creation is idempotent either way).

---

## D-000 — LLM: fully local, no cloud API · Status: accepted (locked)

- **Context:** Air-gapped / offline is a hard product requirement. No API keys, no cloud, no runtime network calls — for the LLM, embeddings, or voice.
- **Decision:** All inference runs locally on the client's hardware. LLM served by Ollama or llama.cpp using GGUF models (start with a Qwen instruct model; stay model-agnostic behind the `llm` adapter). The adapter swaps models/runtimes only, never a provider.
- **Consequences:** (1) Answer quality depends on the local model — mitigated because RAG only asks it to synthesize from retrieved context, not recall facts, so retrieval quality is where effort goes. (2) Hardware must be sized for the model: ~8GB VRAM for a quantized 7–8B model, more for larger. (3) No per-token cost, full privacy, no external dependency. (4) Voice, when added, must be local (Whisper + Piper) — not the browser speech API.

---

## D-001 — Backend framework: FastAPI · Status: accepted

- **Context:** Need async I/O, native streaming (SSE), and a clean, typed API contract that Unity/Quest will depend on.
- **Decision:** FastAPI + pydantic.
- **Consequences:** Python ecosystem for ML is close at hand; the API contract is explicit and versioned.

---

## D-002 — Metadata database: PostgreSQL · Status: accepted

- **Context:** Need reliable storage for users, orgs, document metadata, and logs, with multi-tenant queries.
- **Decision:** PostgreSQL.
- **Consequences:** Solid relational base; `org_id` scoping enforced here and in the vector store.

---

## D-003 — Vector store: metadata-filtering store over raw FAISS · Status: accepted

- **Context:** We are multi-tenant from day one; every query must filter by `org_id`. FAISS is a bare library with no built-in metadata filtering; the original doc named it for v1.
- **Options:** FAISS (fast, bare, DIY metadata) vs Qdrant/Chroma (embedded/local mode, native metadata filtering).
- **Decision:** Start with a store that filters on metadata natively (Qdrant or Chroma in local mode), behind the `vectorstore` adapter.
- **Consequences:** Less custom plumbing for tenancy; reversible because it's behind an adapter. Revisit if scale demands raw FAISS tuning.

---

## D-004 — Streaming transport: SSE · Status: accepted

- **Context:** Web UI and Unity both need token-by-token streaming; simplicity matters early.
- **Decision:** Server-Sent Events for `/v1/chat`.
- **Consequences:** Simple one-way stream that works in browser and Unity. Upgrade to WebSocket only if bidirectional (e.g. live voice) is needed.

---

## D-005 — Multi-tenancy at the data layer from day one · Status: accepted

- **Context:** Retrofitting tenant isolation later is painful and risky.
- **Decision:** Every document, chunk, and query carries `org_id`; the admin UI is deferred but the data boundary is not.
- **Consequences:** Slightly more plumbing now; clean separation and a real "platform" foundation without building the admin features early.
