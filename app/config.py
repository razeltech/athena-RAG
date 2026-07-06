"""Central configuration. Everything is overridable via .env — no hardcoded
secrets, paths, or model names (see rules.md)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Athena"
    environment: str = "dev"

    # --- Database ---------------------------------------------------------
    # Dev default is local SQLite (zero setup). Switch to Postgres for real
    # deployments: postgresql+asyncpg://athena:athena@localhost:5432/athena
    database_url: str = "sqlite+aiosqlite:///./athena.db"

    # --- Auth -------------------------------------------------------------
    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # --- LLM (fully local via Ollama — no API key, no cloud) --------------
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b-instruct"
    # 0.2 kept answers accurate but too flat to carry Athena's tone/personality
    # (verified: the same prompt/model produced personality reliably at 0.5 and
    # not at 0.2 in side-by-side testing). 0.5 is still low enough to stay
    # grounded in the retrieved passages.
    llm_temperature: float = 0.5
    llm_num_ctx: int = 8192

    # --- Embeddings (local sentence-transformers) -------------------------
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Deliberately CPU by default, not auto-detected: this model is small
    # (~130MB) and CPU inference is fast enough that it isn't worth
    # competing with the LLM for GPU memory. sentence-transformers silently
    # grabs CUDA if available and no device is passed — pinning this
    # explicitly is what actually prevents that (see docs/DECISIONS.md D-014).
    embedding_device: str = "cpu"

    # --- Vector store (local Chroma) --------------------------------------
    chroma_dir: str = "./data/chroma"
    retrieval_top_k: int = 5

    # --- Retrieval quality (Phase 3: hybrid search + rerank) ---------------
    # Each of vector search and BM25 keyword search contributes this many
    # candidates before fusion; the reranker then narrows the fused set down
    # to retrieval_top_k for the final answer context.
    hybrid_candidate_k: int = 20
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Same reasoning as embedding_device: small model, CPU by default, GPU
    # memory reserved for the LLM (and later, the GPU-tier TTS engine).
    reranker_device: str = "cpu"

    # --- Resource management (see docs/DECISIONS.md D-014) -----------------
    # The one shared local GPU is a scarce, contended resource once the LLM
    # (Ollama), and later voice, are all in the picture — nothing should grab
    # it just because it happens to be available.
    #
    # How long Ollama keeps the LLM resident in VRAM after the last request
    # before unloading it. Ollama's own default (5m) is left implicit today;
    # setting it explicitly here makes the tradeoff a deliberate choice, not
    # an accident: shorter frees VRAM sooner for other local models (e.g. a
    # GPU-tier TTS engine) at the cost of a reload delay on the next chat
    # message; longer avoids reload latency but holds VRAM even when idle.
    llm_keep_alive: str = "5m"
    # Caps CPU threads used by torch-based local models (embedder, reranker,
    # and later faster-whisper/Indic Parler-TTS on CPU) so they don't
    # unconditionally grab every core — important on lower-end hardware
    # where that would starve FastAPI's own event loop. None = leave
    # torch's own default (usually all logical cores) alone.
    cpu_thread_limit: int | None = None

    # --- Chunking (word-based for now; swap to token-based later) ---------
    chunk_size: int = 800
    chunk_overlap: int = 150

    # --- Uploads ----------------------------------------------------------
    upload_dir: str = "./data/uploads"


settings = Settings()
