# Project Athena

A **fully local, offline** RAG platform. Ask questions about your own documents and
get grounded, cited answers — no API keys, no cloud, everything runs on your hardware.
The API is the product: a Claude-style web page is the first client; a Unity/Meta Quest
app is a later client using the same API.

> Read `rules.md` and `docs/PLAN.md` before building. They keep scope and architecture on track.

## Starting the server yourself (day-to-day)

The environment is already set up (`.venv`, `.env`, dependencies installed). Every time you
want to run/test the app locally, you only need two things running:

1. **Ollama** (the local LLM engine) — if it's not already running:
   ```powershell
   ollama list   # starts the Ollama background service if it wasn't already running
   ```
2. **The Athena server** — in this project folder:
   ```powershell
   .venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --port 3636
   ```
   (Git Bash / WSL: `source .venv/Scripts/activate && uvicorn app.main:app --reload --port 3636`)

Then open **http://localhost:3636** in your browser. `--port 3636` matches what's been used
during development in this repo so far — change it (or drop the flag for the default 8000)
if you prefer. `--reload` auto-restarts the server whenever a `.py` file changes, so you
generally don't need to stop/restart it yourself while iterating on backend code — only
`web/index.html` changes need just a browser refresh, no restart at all.

To stop the server, `Ctrl+C` in that terminal.

## Stack

| Concern      | Choice (all local)                              | Swappable via |
|--------------|--------------------------------------------------|---------------|
| API          | FastAPI, versioned `/v1`, SSE streaming          | —             |
| LLM          | Ollama + GGUF (default `qwen2.5:7b-instruct`)    | `app/adapters/llm/` |
| Embeddings   | sentence-transformers (`bge-small-en-v1.5`)      | `app/adapters/embeddings/` |
| Vector store | Chroma (persistent, metadata-filtered by org)    | `app/adapters/vectorstore/` |
| Retrieval    | Hybrid: vector + BM25 keyword, fused (RRF)       | `app/services/hybrid_search.py` |
| Reranker     | Local cross-encoder (`ms-marco-MiniLM-L-6-v2`)   | `app/adapters/reranker/` |
| Parsers      | txt / md / html / docx / xlsx / csv / pdf         | `app/adapters/parsers/` |
| Metadata DB  | SQLite (dev) / PostgreSQL (prod)                 | `DATABASE_URL` |

Everything model-related sits behind an interface in `app/core/`. Swapping an
implementation should touch only its adapter folder.

## Hardware (RTX 3060 12GB)

- `qwen2.5:7b-instruct` — ~5GB VRAM, fast. Good default.
- `qwen2.5:14b-instruct-q4_K_M` — ~9GB VRAM, slower but noticeably smarter. Set it in `.env`.

For grounded document Q&A (synthesizing from retrieved passages, not free reasoning),
the 14B model is genuinely strong on a 3060.

## Quickstart

1. **Install Ollama** and pull a model:
   ```
   ollama pull qwen2.5:7b-instruct
   ```
2. **Python env + deps:**
   ```
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Config:**
   ```
   cp .env.example .env      # then edit JWT_SECRET
   ```
4. **Run:**
   ```
   uvicorn app.main:app --reload
   ```
   DB tables (and a default org) are created automatically on startup. `python -m scripts.init_db`
   still exists for manual/CI use (e.g. pre-provisioning a real Postgres DB before first boot).
5. Open **http://localhost:8000**, add a document (txt / md / html / docx / xlsx / csv / pdf),
   and ask a question.

> First run downloads the embedding model (~130MB) once, then works fully offline.
> For an air-gapped server, pre-stage that model.

## Adding a document format

1. Create a parser in `app/adapters/parsers/` implementing `DocumentParser`
   (copy `text_parser.py`).
2. Register it in `app/adapters/parsers/registry.py`.

Nothing else changes. txt/md/html/docx/xlsx/csv/pdf are done; PPTX is the
remaining item from the original suggested order (docx, pptx, xlsx, csv, then
PDF — hardest, done last). Note: emails, SharePoint, Confluence, and SQL are
**connectors**, not parsers — a separate, later effort (auth, sync, permissions).

## API (v1)

| Method | Path                                  | Purpose                                     |
|--------|---------------------------------------|----------------------------------------------|
| POST   | `/v1/auth/login`                      | Dev login → JWT (with `org_id`)              |
| POST   | `/v1/documents`                       | Upload + ingest a file                       |
| GET    | `/v1/documents/supported`             | List supported file types                    |
| GET    | `/v1/documents`                       | List uploaded documents for your org         |
| DELETE | `/v1/documents/{doc_id}`              | Delete a document (chunks + record + file)   |
| GET    | `/v1/conversations`                   | List your org's conversations                |
| GET    | `/v1/conversations/{id}/messages`     | Replay a conversation's full message history |
| DELETE | `/v1/conversations/{id}`              | Delete a conversation                        |
| POST   | `/v1/chat`                            | Ask a question (SSE stream), conversation-scoped |
| GET    | `/v1/health`                          | Health check                                  |

The **same API** is what the Unity/Quest client will call — keep the contract stable.
`/v1/chat` persists and loads history server-side via `conversation_id` (see
`docs/DECISIONS.md` D-007) — clients no longer resend the full message history each turn.

## Tests

```
pytest
```

## Evaluating retrieval quality

```
python -m scripts.eval docs/eval_set.example.json --org-id org_default --with-llm
```

`docs/eval_set.example.json` is a format example, not a real benchmark — copy it and
replace with real questions + expected source documents from your own ingested files.
See `docs/PLAN.md` §7.

## Project layout

```
app/
  core/         interfaces (llm, embeddings, vectorstore, parser) + domain models
  adapters/     local implementations of each interface
  services/     chunking, ingest, rag orchestration
  api/          auth, DI, v1 routes (health, auth, documents, chat)
  db/           SQLAlchemy models + async session
web/            the chat UI
tests/          starter tests
docs/           PLAN.md, DECISIONS.md
rules.md        rules the AI coding assistant must follow
```
