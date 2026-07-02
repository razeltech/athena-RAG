from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.database import SessionLocal, engine
from app.db.models import Base, Organization
from app.logging_conf import configure_logging
from app.api.v1.router import api_router

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB tables are no longer optional (documents/conversations depend on them),
    # so create them automatically instead of requiring a manual script run.
    # scripts/init_db.py still exists for CI / pre-provisioning a real Postgres DB.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        if await session.get(Organization, "org_default") is None:
            session.add(Organization(id="org_default", name="Default Org"))
            await session.commit()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# DEV: wide-open CORS so the web page and (later) Unity can call the API.
# Tighten allow_origins for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Versioned API — Unity/Quest depend on this contract, so keep it stable.
app.include_router(api_router, prefix="/v1")

# Serve the web UI at "/". API routes above are matched first.
app.mount("/", StaticFiles(directory="web", html=True), name="web")
