import logging
import os
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org, get_db_session, get_ingest_service, get_vectorstore
from app.config import settings
from app.core.vectorstore import VectorStore
from app.db.models import Document
from app.services.ingest import IngestService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    org_id: str = Depends(get_current_org),
    ingest: IngestService = Depends(get_ingest_service),
):
    os.makedirs(settings.upload_dir, exist_ok=True)
    dest = os.path.join(settings.upload_dir, f"{org_id}__{file.filename}")
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    try:
        return await ingest.ingest_file(dest, file.filename, org_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/documents/supported")
async def supported_types(
    ingest: IngestService = Depends(get_ingest_service),
):
    return {"supported": ingest.registry.supported()}


@router.get("/documents")
async def list_documents(
    org_id: str = Depends(get_current_org),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    result = await session.execute(
        select(Document).where(Document.org_id == org_id).order_by(Document.created_at.desc())
    )
    return [
        {
            "id": d.id,
            "source": d.source,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at.isoformat(),
        }
        for d in result.scalars().all()
    ]


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    org_id: str = Depends(get_current_org),
    session: AsyncSession = Depends(get_db_session),
    vectorstore: VectorStore = Depends(get_vectorstore),
):
    result = await session.execute(
        select(Document).where(Document.id == doc_id, Document.org_id == org_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        # 404, not 403 — don't leak whether another org's document exists.
        raise HTTPException(status_code=404, detail="Document not found")

    # Least-reversible steps first: if the DB commit below fails, an orphaned
    # DB row (harmless, just re-deletable) is a better failure mode than
    # orphaned vector chunks / files with no record left to find them by.
    vectorstore.delete_document(org_id, doc_id)
    file_path = os.path.join(settings.upload_dir, f"{org_id}__{doc.source}")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            # e.g. Windows file lock from an antivirus/indexer scan — the
            # document is already gone from retrieval either way; don't let
            # a stray locked file block that. Leaves a harmless orphaned file
            # to clean up later instead of leaving the document "un-deletable."
            logger.warning("Could not remove uploaded file %s: %s", file_path, e)

    await session.delete(doc)
    await session.commit()
    return {"deleted": doc_id}
