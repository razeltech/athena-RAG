"""Dependency injection. Heavy singletons (embedder, vector store, llm) are
cached so the embedding model loads once."""
from functools import lru_cache
from typing import AsyncIterator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.embeddings.sentence_transformers_embedder import (
    SentenceTransformerEmbedder,
)
from app.adapters.llm.ollama_llm import OllamaLLM
from app.adapters.parsers.registry import ParserRegistry
from app.adapters.reranker.cross_encoder_reranker import CrossEncoderReranker
from app.adapters.vectorstore.chroma_store import ChromaVectorStore
from app.api.auth import decode_token
from app.db.database import SessionLocal
from app.services.ingest import IngestService
from app.services.rag import RagService


@lru_cache
def get_embedder() -> SentenceTransformerEmbedder:
    return SentenceTransformerEmbedder()


@lru_cache
def get_vectorstore() -> ChromaVectorStore:
    return ChromaVectorStore()


@lru_cache
def get_llm() -> OllamaLLM:
    return OllamaLLM()


@lru_cache
def get_registry() -> ParserRegistry:
    return ParserRegistry()


@lru_cache
def get_reranker() -> CrossEncoderReranker:
    return CrossEncoderReranker()


def get_ingest_service(
    embedder: SentenceTransformerEmbedder = Depends(get_embedder),
    vectorstore: ChromaVectorStore = Depends(get_vectorstore),
    registry: ParserRegistry = Depends(get_registry),
) -> IngestService:
    # Dependencies come in via Depends(...) params (not plain get_x() calls)
    # so that app.dependency_overrides on get_vectorstore/get_embedder/etc.
    # actually cascades here — a bare function call inside the body would
    # silently bypass any override and hit the real cached singleton.
    return IngestService(embedder, vectorstore, registry)


def get_rag_service(
    embedder: SentenceTransformerEmbedder = Depends(get_embedder),
    vectorstore: ChromaVectorStore = Depends(get_vectorstore),
    llm: OllamaLLM = Depends(get_llm),
    reranker: CrossEncoderReranker = Depends(get_reranker),
) -> RagService:
    return RagService(embedder, vectorstore, llm, reranker)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_current_org(authorization: str = Header(default="")) -> str:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    org_id = payload.get("org_id")
    if not org_id:
        raise HTTPException(status_code=401, detail="Token missing org_id")
    return org_id
