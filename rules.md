# Project Athena — Working Rules

> Temporary codename. This file is read by the AI coding assistant **at the start of every session** and before proposing any change. Keep it short, keep it obeyed.

---

## What we are building

An **API-first RAG platform**. A user asks a question in natural language; the system retrieves the relevant pieces from *their own ingested documents* (many file formats) and answers **with citations**. The **API is the product**. The first client is a web chat UI that looks and streams like Claude/ChatGPT. The **same API** is later consumed by a Meta Quest 2/3 app built in Unity.

---

## Prime Directive — do not drift

Every feature must serve one loop:

> **ingest documents → retrieve relevant chunks → generate a grounded, cited answer → stream it to any client over one shared API.**

If a proposed feature does not make that loop *more accurate, more usable, or usable by another client*, it does not belong in the current scope. Say so instead of building it.

---

## In scope right now (Phases 1–3: done. Phase 4: next, per `docs/PLAN.md` §10)

Phases 1–3 are built: ingestion/extraction for common formats, chunking + embeddings + vector storage per org, hybrid (vector + BM25) retrieval with reranking, cited streaming answers, and data-level multi-tenancy. Phase 4 is the confirmed next work, in this order:
1. Answer tone/personality (Athena's own persona — not a copy of any existing fictional assistant).
2. Voice — **confirmed required for the final build** (not hypothetical anymore). Local `/v1/transcribe` (Whisper) + `/v1/speak` (Piper) only — never the browser Speech API, which can route audio to the cloud and breaks offline.
3. Unordered, as-needed: OCR, bulk upload, real per-user logins/profiles, packaging/installer for distribution.

## Deferred — do NOT build yet

Knowledge graph · AI agents (email/db/web/automation) · Quest/Unity SDK package · plugin SDK · org-admin analytics dashboards · model fine-tuning.

Do **not** add code, folders, dependencies, or abstractions "in preparation" for anything on this list. When a task drifts toward it, stop and flag it.

---

## Architecture seams that MUST stay swappable

Each of these sits behind an interface with exactly **one** implementation for now. No other module may import an implementation directly — only its interface.

- **LLM provider** (chat completion + token streaming)
- **Embedding model**
- **Vector store**
- **Document parser** (per file type, behind one shared `extract()` contract)
- **Reranker** (Phase 3 — built)

The `LLM provider` seam exists so we can swap **local models** freely (Qwen → Gemma → Llama, or Ollama → llama.cpp → vLLM) with no other code changes. It is **never** a cloud API. Protect it.

---

## Non-negotiables

- **Fully local / air-gapped.** No external API calls, no API keys, no cloud services for inference, embeddings, models, or voice. Nothing at runtime may require an internet connection. If a library needs a network call to work, it's the wrong library.
- Every answer returns **citations** (source document + location). No citation = a bug, not a style choice.
- **Streaming from day one** (SSE). The web UI renders tokens as they arrive.
- **Multi-tenant at the data layer from the start**: every document, chunk, and query carries an `org_id`. (The admin *UI* is deferred; the data boundary is not.)
- Every architectural choice gets an entry in `/docs/DECISIONS.md`.
- Every new capability ships with at least one test proving it works end to end.
- The public API is **versioned** (`/v1/...`) because Unity/Quest will depend on the contract.

---

## Coding conventions

- Backend: **Python 3.11+, FastAPI**, async on anything that touches I/O.
- Type hints everywhere. **Pydantic** models for every API request/response shape.
- One module = one responsibility. Interfaces live in a `core/` (ports) layer; implementations live in `adapters/`.
- All config through a single settings object / environment — **no hardcoded** secrets, paths, or model names.
- Prefer editing an existing file over creating a parallel new one.

---

## How the assistant should work in this repo

1. Read this file and `/docs/PLAN.md` before proposing changes.
2. Before adding a dependency, module, or abstraction: check it against the **Prime Directive** and the **Deferred** list. If it's deferred, stop and say so.
3. For any non-trivial decision, propose **1–2 options with the trade-off**, then record the chosen one in `/docs/DECISIONS.md`.
4. Keep `/docs` in sync with code **in the same change**.
5. **Ask first** before: changing the API contract, swapping a core adapter, or touching anything on the Deferred list.

---

## Definition of done (per feature)

Works end to end through the API · has a test · returns citations if it touches answering · `PLAN.md` + `DECISIONS.md` updated · a real web-client user could actually use it.
