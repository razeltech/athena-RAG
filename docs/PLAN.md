# Project Athena — Plan

> Temporary codename. This is the plan we build against. It intentionally stops at Phase 3. We extend it only after the core RAG loop is validated with the real client.

---

## 1. Vision (honest version)

Build an API-first platform that lets an organization ask questions about its **own documents** and get **grounded, cited answers**, streamed to any client. First client: a Claude-style web chat page. Second client: a Meta Quest 2/3 app in Unity, using the **same API**.

**Hard constraint (locked):** everything runs **fully local / air-gapped** — no API keys, no cloud, no network calls at runtime. The LLM, embeddings, and (later) voice all run on the client's own hardware.

**The trade-off we accept:** a local model won't match Claude/ChatGPT at open-ended reasoning. But in RAG the model isn't recalling facts from memory — it **synthesizes an answer from the exact chunks we retrieve and hand it**. That's a far easier task, and a good 7B–14B instruct model (Qwen, Gemma, Llama) does it well. So the practical quality gap is small for "answer from these passages, with citations" — which is exactly our use case. The cost of going local is that **retrieval quality matters even more**, and that hardware must be sized for the model.

**Hardware reality:** a 7B–8B model quantized (e.g. Q4) needs roughly 8GB of VRAM to run at a usable speed; larger models need proportionally more. The deployment box (server/PC on the client's premises) must be spec'd for the chosen model — this is a client conversation to have early.

**Deployment reality for Quest:** the headset cannot run the model. The API + models run on the on-prem server/PC; the web browser and the Quest app both call it over the local network. "Offline" means no internet dependency — not model-on-device.

---

## 2. Scope

**In now (Phases 1–3):** ingestion + extraction, chunking, embeddings, per-org vector storage, retrieval, cited answer generation, streaming chat API, and a plain web UI.

**Deferred (see `rules.md`):** knowledge graph, AI agents, Quest/Unity SDK package, plugin SDK, admin analytics, fine-tuning, server-side voice.

---

## 3. Architecture (lean)

```
 Clients        Web (HTML/JS)   |   Unity / Quest   |   (later: mobile, CLI)
                          \             |            /
                           \            |           /
 API (FastAPI, /v1)   REST + SSE streaming · auth · org routing · request logging
                                        |
 Orchestration       build prompt · retrieve · call LLM (stream) · attach citations
                                        |
 Knowledge           vector search  →  (Phase 3) hybrid search + reranker
                                        |
 Adapters (swappable)  LLM provider · embedding model · vector store · doc parsers
                                        |
 Storage             PostgreSQL (users, orgs, doc metadata, logs) · vector store · file store
```

Everything in **Adapters** is reachable only through an interface. That is the whole flexibility story — no leakage into other layers.

---

## 4. Modules (only what Phases 1–3 need)

- **api** — FastAPI app, routing, auth, SSE streaming, versioned `/v1`.
- **auth** — login + JWT, `org_id` attached to every request.
- **ingest** — accept a file, route to the right parser, return clean text + metadata.
- **parsers** — one `extract(file) -> Document` contract; a small implementation per format.
- **chunking** — token-aware splitter with overlap; preserves source location for citations.
- **embeddings** — adapter around a local embedding model.
- **vectorstore** — adapter; store/query chunks with `org_id` metadata filtering.
- **retrieval** — top-k search now; hybrid + rerank in Phase 3.
- **orchestrator** — assemble prompt from retrieved chunks, call the LLM adapter, stream tokens, return citations.
- **llm** — adapter (chat + streaming). First implementation: Claude API. Later: local.
- **web** — the chat page.

Anything not on this list is out of scope until the plan is extended.

---

## 5. Technology choices (with one-line reasons)

- **FastAPI** — async, first-class streaming (SSE), clean pydantic contracts for the API that Unity will depend on.
- **PostgreSQL** — reliable store for users, orgs, document metadata, logs.
- **Local embedding model** (e.g. a small `sentence-transformers` / BGE-class model) — embeddings can be local and cheap even when the answer LLM is cloud.
- **Vector store with metadata filtering** — because we are multi-tenant from day one, prefer a store that supports `org_id` filtering natively (e.g. Qdrant or Chroma in embedded/local mode) over raw FAISS. Kept behind the `vectorstore` adapter, so this is reversible. *(Recorded in DECISIONS.md — this is a change from the original FAISS suggestion.)*
- **LLM: fully local via adapter** — served by Ollama or llama.cpp, running GGUF models (start with a Qwen instruct model; stay model-agnostic). The adapter swaps *models and runtimes*, never a cloud provider. *(Locked — see DECISIONS.md.)*
- **SSE for streaming** — simplest way to stream tokens to the browser and to Unity; upgrade to WebSocket only if we need bidirectional (e.g. live voice).

---

## 6. Phases (concrete, with acceptance criteria)

### Phase 1 — Foundation
Project structure, settings/config, PostgreSQL, JWT auth with `org_id`, request logging, a health endpoint, and a stub `/v1/chat` that streams a hardcoded reply over SSE.
**Done when:** you can log in, hit `/v1/chat`, and watch tokens stream into a bare web page.

### Phase 2 — Ingestion + retrieval
`extract()` contract + parsers for the first formats, chunking with source locations, embeddings, vector store with `org_id` filtering, and a real retrieval step feeding the LLM.
**Done when:** you upload a document, ask a question, and get an answer built from *that* document, **with citations** pointing back to it.

Also added in this round (not originally itemized, but a natural extension once the core loop was validated): document management (list/delete an ingested document, with its chunks/DB record/file all removed together) and server-persisted, resumable chat history (see `docs/DECISIONS.md` D-006/D-007).

### Phase 3 — Quality
Hybrid search (vector + keyword), a reranker, and citation formatting the UI can render nicely. Plus the evaluation harness in §7.
**Done when:** on your client's real documents, the eval set hits your agreed accuracy/latency bar.

**Built:** vector search + BM25 keyword search, fused by Reciprocal Rank Fusion (`app/services/hybrid_search.py`), then reranked by a local cross-encoder (`app/core/reranker.py` + `app/adapters/reranker/`) down to the final context size. Citation rendering already got a UI pass in the Phase 2 round (collapsible sources). The eval harness (`scripts/eval.py` + `docs/eval_set.example.json`) measures retrieval hit-rate and latency against whatever's actually ingested in a deployment.

**Scope note:** running that harness against real documents/questions and deciding what accuracy/latency bar is "good enough" is each **deployment's** job, not something built centrally into the product. Razel Tech's product is the API/platform itself — clients bring their own data, host it themselves, and it never leaves their machine (that's the whole point of "fully local"). The harness is provided as self-serve tooling for whoever operates a given deployment (the client, or Razel Tech during setup/onboarding) to check quality on their own documents if they want to — it is not a gate Razel Tech needs to clear centrally before Phase 3 counts as "done." Phase 3 is done: the retrieval-quality mechanisms exist and are verified working.

---

## 7. Evaluation (the part the original plan skipped)

RAG lives or dies on retrieval quality, so we measure it, not vibe-check it.

- Build a small **eval set** with the real client: ~20–50 real questions, each with the correct source passage(s).
- Track: **retrieval hit-rate** (did the right chunk come back?), **answer groundedness** (is every claim cited?), and **latency** (time to first token, total time).
- Set one concrete bar with the client before Phase 3, e.g. "correct source in top-k ≥ 90%, answer streams first token < 2s." Adjust to their reality.
- Re-run the eval on every change that touches chunking, embeddings, retrieval, or the model.

**Tooling:** `python -m scripts.eval docs/eval_set.example.json --org-id <your org> [--with-llm]`. Retrieval hit-rate + latency are measured automatically. `--with-llm` adds time-to-first-token/total latency and prints each generated answer next to its citations for a manual groundedness spot-check — auto-verifying that every claim in an answer is actually supported by its citations is a hard NLP problem on its own, out of scope here.

---

## 8. Document formats — sequencing

Start with the **easiest** formats to prove the pipeline fast, then widen:

1. First: **Markdown / plain text / HTML** — near-zero extraction pain, so you're testing retrieval, not parsing. **Done.**
2. Then: **DOCX, XLSX, CSV** — structured but well-supported by libraries. **Done.** (PPTX not yet built.)
3. Then: **PDF** — hardest (scans, columns, tables, OCR). Deliberately not first. **Done** for text-layer PDFs; scanned/image-only PDFs raise a clear error (no OCR yet).

Note the split the original list blurred: DOCX/XLSX/PPTX/HTML/MD/CSV are **file formats** (just "extract text well"). **Emails, SharePoint, Confluence, SQL databases** are **data-source connectors** — a different problem (auth, permission mapping, sync, incremental updates) and each is its own project. Treat connectors as a later, separately-scoped phase, not as "one more format."

---

## 9. Clients

- **Web first** — plain HTML/CSS/JS chat page that consumes the SSE stream and renders citations. Looks/behaves like Claude/ChatGPT.
- **Quest/Unity later** — a Unity (C#) app that makes the same HTTP + SSE calls to the same `/v1` API. Nothing model-related lives on the headset. This is *why* we keep the API contract stable and versioned.
- **Voice** — must be **local**, not the browser speech API (which can send audio to the cloud). When a client needs voice, add `/v1/transcribe` (local Whisper) and `/v1/speak` (local Piper) so every client shares the same offline pipeline.

---

## 10. Phase 4 (planned, after Phase 3 — recorded per rules.md before building)

Phases 1–3 target technical correctness. Phase 4 targets making the product genuinely usable at real scale (colleges/schools/offices) and market-ready. Strict order — each item starts only after the one above it is solid:

1. **Answer tone/personality** — **Done.** `SYSTEM_PROMPT` (`app/services/rag.py`) now gives Athena her own original persona (not a copy of any existing fictional assistant) — warm, natural, with genuine Telugu/Andhra-Telangana touches (e.g. "Ayyo") used sparingly and only when it actually fits, verified working live against the real model. Getting this to actually land took two things together, not just a prompt rewrite — see `docs/DECISIONS.md` D-009 (a concrete worked example beat an abstract description, and `llm_temperature` moved from 0.2 to 0.5). Next: broaden to other regions' common expressions over time.
2. **Voice** — confirmed as a hard requirement for the final build (a selling point), sequenced after tone work so it sits on top of an assistant that already sounds good. Local Whisper (`/v1/transcribe`) + local Piper (`/v1/speak`) per the existing rule — never the browser Speech API. **Next up.**
3. **As-needed, unordered** (each gets its own scoping pass and `DECISIONS.md` entry when picked up):
   - **OCR** for scanned/image-only PDFs (batch, at ingest time — not live/video capture). Not on the "do not build" list, just not yet reached.
   - **Bulk upload** (many files / a folder at once) — the single-file upload UI doesn't scale past a handful of documents.
   - **Real per-user logins + individual profiles** (ChatGPT/Claude-style) — replace the dev-only login stub with real password verification against the existing `users` table, and scope `Conversation`/`Document` by `user_id` in addition to `org_id`.
   - **Packaging/distribution** — ship an installable build (not raw source) that sets up the environment automatically, so a non-technical client can run it. `docker-compose.yml` already covers the "technical user" path; a native installer is a separate, bigger effort.

Nothing above changes Phases 1–3's scope or the Prime Directive — it's the ordered backlog for after Phase 3 ships.
