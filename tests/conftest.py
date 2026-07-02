"""Shared test fixtures.

`app/config.py`'s `settings` and `app/api/deps.py`'s `@lru_cache`d singletons
are both created at import time, so per-test isolation via `monkeypatch.setenv`
won't reliably reach code that already did `from app.config import settings`
(a name binding, not a live reference). Using FastAPI's `dependency_overrides`
instead sidesteps that entirely — each test gets its own throwaway DB engine
and Chroma directory without fighting any global state. The app's startup
`lifespan` (table creation + default-org upsert) still runs against whatever
`app.main.engine`/`SessionLocal` point at, so those get monkeypatched too —
otherwise TestClient's startup would touch the real dev `athena.db`.
"""
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.vectorstore.chroma_store import ChromaVectorStore
from app.api.deps import get_db_session, get_vectorstore
from app.config import settings
from app.main import app


@pytest_asyncio.fixture
async def test_db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, session_factory
    await engine.dispose()


@pytest.fixture
def client(tmp_path, test_db, monkeypatch):
    engine, session_factory = test_db
    test_store = ChromaVectorStore(persist_dir=str(tmp_path / "chroma"))

    async def _override_db_session():
        async with session_factory() as session:
            yield session

    monkeypatch.setattr("app.main.engine", engine)
    monkeypatch.setattr("app.main.SessionLocal", session_factory)
    monkeypatch.setattr("app.services.ingest.SessionLocal", session_factory)
    monkeypatch.setattr("app.api.v1.chat.SessionLocal", session_factory)
    # `settings` is a single shared instance — mutating its attribute (rather
    # than rebinding the module-level name) reaches every module that already
    # did `from app.config import settings`.
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))

    app.dependency_overrides[get_vectorstore] = lambda: test_store
    app.dependency_overrides[get_db_session] = _override_db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    resp = client.post(
        "/v1/auth/login", json={"username": "dev", "password": "dev"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
