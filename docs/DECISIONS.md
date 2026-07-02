# Decision Log

Every important choice gets an entry so that in six months — or when a second developer joins — you know *why*, not just *what*. Newest at the top.

**Format:** each entry has Context · Options · Decision · Consequences · Status (`accepted` / `open` / `superseded`).

---

## D-011 — Embedding/reranker models load with `local_files_only=True` · Status: accepted

- **Context:** A user-reported slow first message ("hey" took 18.2s) turned out to be partly a real bug, not just cold-start model loading: `sentence-transformers` was making live HEAD requests to huggingface.co on every process start to check for model updates, even though the model was already downloaded and cached. That's a genuine violation of `rules.md`'s non-negotiable — "nothing at runtime may require an internet connection" — not just a performance nit.
- **Decision:** Both `SentenceTransformerEmbedder` and `CrossEncoderReranker` now try loading with `local_files_only=True` first (zero network calls), falling back to a normal load only if that raises `OSError` (i.e. genuinely first run, nothing cached yet — matches the README's documented "first run downloads the model once" behavior).
- **Consequences:** Verified — cold start (first request after a restart) dropped from ~18s to ~8.8s (now pure model-loading time, no network round-trips); warm requests are ~1.2s. The full test suite dropped from ~40s to ~7.4s for the same reason. No behavior change for a genuinely fresh install — the fallback still allows the one-time download.

---

## D-010 — Personas + Modes engine (data-driven, not hardcoded) · Status: accepted

- **Context:** A single hardcoded `SYSTEM_PROMPT` string doesn't scale — the user wants multiple selectable personas (Athena, Meera, Smiley, Raza, with more to come later — "N numbers we can build later"), independently combined with selectable answer-shape modes (teaching, explaining, reviewing code, etc.), switchable per conversation and mid-conversation, plus a response habit (always close with a relevant follow-up, not just stop dead) and lightweight style-mirroring of how the user talks.
- **Decision:** Two small data-driven registries — `app/services/personas.py` (tone/identity) and `app/services/modes.py` (answer shape) — same registry pattern already used elsewhere in this codebase (e.g. `ParserRegistry`). `RagService._build_system_prompt()` composes: persona prompt + mode prompt + shared grounding/citation rules + a style hint derived from the user's last few messages in that conversation (no persistent profile, no training — just noticing this conversation's phrasing) + the current clock fact. `Conversation` gained `persona`/`mode` columns (default `athena`/`answering`), settable via `ChatRequest` and switchable on any turn. New `GET /v1/personas` and `GET /v1/modes` list what's available; the web UI exposes both as header dropdowns.
- **Consequences:** Adding persona/mode N+1 later is "add an entry to the registry," not a code change elsewhere in the app. Each persona's prompt carries its own single worked example combining tone + citation + the follow-up habit — confirmed (D-009) that a combined concrete example is what actually makes a 7B model reliably do multiple instructions at once, not an abstract list of rules. Style-mirroring is intentionally shallow (last 3 user messages, recomputed each turn) — a persistent per-user style profile would be a bigger, separate feature if ever wanted. Migration note: `Base.metadata.create_all` only creates missing tables, never alters an existing one — a real deployment's already-existing `conversations` table needed the new columns added by hand. Added a tiny portable `ensure_column()` helper (`app/db/database.py`) for this rather than pulling in Alembic; revisit that call once schema changes get more frequent than a handful of additive columns.

## D-009 — Athena's persona (Phase 4, item 1): prompt structure + temperature · Status: accepted

- **Context:** Phase 4 called for Athena's own natural, warm tone (with tasteful Telugu/Andhra-Telangana touches), not a robotic compliance-instruction voice. First attempt (personality described abstractly, appended after the grounding/citation rules, at `llm_temperature=0.2`) produced zero observable personality across repeated tests — confirmed via a side-by-side diagnostic: the exact same persona instruction, on the same model, produced clear personality when given as the *only* instruction, but vanished once combined with the citation/grounding rules in the actual RAG prompt structure.
- **Decision:** Two changes, both required together (neither alone was sufficient in testing): (1) give the model a **concrete example** of the target tone combined with a citation in the same reply, rather than an abstract description — small instruct models follow worked examples far more reliably than adjectives — and explicitly state the persona is "not optional, apply it the same way you'd never skip a citation" so it doesn't get deprioritized against the grounding rules; (2) raise `llm_temperature` from 0.2 to 0.5 — 0.2 was low enough to suppress natural-sounding phrasing entirely. `SYSTEM_PROMPT` in `app/services/rag.py`; default in `app/config.py` and `.env.example`.
- **Consequences:** Verified working via repeated live tests against the real model (`qwen2.5:7b-instruct`) — citations and grounding are unaffected (still cites correctly, still says "I don't have that information" when the context doesn't cover it). Smaller/future local models may need this re-tuned; re-verify by hand when swapping `LLM_MODEL`, not just by reading the prompt. A real, non-obvious gotcha hit while doing this work, worth recording so it isn't rediscovered the hard way: **`uvicorn --reload` must actually be passed** — a manual restart without it silently keeps serving old code/env after edits, which looked exactly like "the prompt change didn't work" for several rounds of testing before the real cause (missing flag) was found.

- **Context:** Vector search alone misses exact-term matches (model numbers, names, acronyms) that embeddings blur together — the known weak spot `rules.md`'s Phase 3 scope calls "hybrid search" out to fix. Also needed a reranker seam, since `rules.md`'s architecture-seams list names one explicitly for Phase 3.
- **Options considered for the keyword half:** (a) SQLite FTS5 (already have SQLite, but needs raw-SQL virtual-table wiring outside the SQLAlchemy ORM) vs (b) `rank_bm25`, a pure-Python BM25 implementation scored in-memory against `VectorStore.get_all(org_id)` (a new method added to the `VectorStore` interface, since the vector store already holds full chunk text). Chose (b) for simplicity — no new schema/migration, and at the "hundreds to low-thousands of chunks per org" scale this project targets, rebuilding the BM25 index per query is fast (~tens of ms, confirmed in testing) with no persistence to manage.
- **Decision:** `app/services/hybrid_search.py` provides `bm25_search()` and `reciprocal_rank_fusion()` (RRF — fuses by rank position, not raw score, since BM25 and cosine-similarity scores aren't on comparable scales). `RagService.retrieve()` now: vector search top-N + BM25 top-N → RRF fuse → rerank fused candidates with a local `sentence-transformers` `CrossEncoder` (`cross-encoder/ms-marco-MiniLM-L-6-v2`, same library already used for embeddings, ~80MB, downloaded once) down to the final `retrieval_top_k`. New settings: `hybrid_candidate_k` (candidates per method before fusion, default 20), `reranker_model`.
- **Consequences:** One new interface (`app/core/reranker.py`, matching the existing adapter pattern) with one local implementation — swappable later without touching `RagService`. Retrieval is slightly slower per query (BM25 pass + cross-encoder pass, both local/CPU), acceptable given retrieval quality was the explicit Phase 3 goal. `scripts/eval.py` exists specifically to measure whether this tradeoff is worth it on real documents.

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
