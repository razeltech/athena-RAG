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
    llm_temperature: float = 0.2
    llm_num_ctx: int = 8192

    # --- Embeddings (local sentence-transformers) -------------------------
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # --- Vector store (local Chroma) --------------------------------------
    chroma_dir: str = "./data/chroma"
    retrieval_top_k: int = 5

    # --- Retrieval quality (Phase 3: hybrid search + rerank) ---------------
    # Each of vector search and BM25 keyword search contributes this many
    # candidates before fusion; the reranker then narrows the fused set down
    # to retrieval_top_k for the final answer context.
    hybrid_candidate_k: int = 20
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- Chunking (word-based for now; swap to token-based later) ---------
    chunk_size: int = 800
    chunk_overlap: int = 150

    # --- Uploads ----------------------------------------------------------
    upload_dir: str = "./data/uploads"


settings = Settings()
