import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org, get_db_session, get_rag_service
from app.core.models import ChatMessage
from app.db.database import SessionLocal
from app.db.models import Conversation, Message
from app.services.rag import RagService

TITLE_MAX_LEN = 60


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None  # None => start a new conversation


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


router = APIRouter()


async def _load_history(session: AsyncSession, conversation_id: str) -> list[ChatMessage]:
    result = await session.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.seq)
    )
    return [ChatMessage(role=m.role, content=m.content) for m in result.scalars().all()]


@router.post("/chat")
async def chat(
    req: ChatRequest,
    org_id: str = Depends(get_current_org),
    rag: RagService = Depends(get_rag_service),
    session: AsyncSession = Depends(get_db_session),
):
    is_new = req.conversation_id is None
    if is_new:
        conversation = Conversation(org_id=org_id)
        session.add(conversation)
        await session.flush()  # populate conversation.id without committing yet
    else:
        result = await session.execute(
            select(Conversation).where(
                Conversation.id == req.conversation_id, Conversation.org_id == org_id
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

    history = await _load_history(session, conversation.id)

    if is_new:
        title = req.message[:TITLE_MAX_LEN]
        if len(req.message) > TITLE_MAX_LEN:
            title += "…"
        conversation.title = title

    base_seq_result = await session.execute(
        select(func.count()).select_from(Message).where(Message.conversation_id == conversation.id)
    )
    base_seq = base_seq_result.scalar_one()

    session.add(
        Message(conversation_id=conversation.id, role="user", content=req.message, seq=base_seq)
    )
    await session.commit()

    messages, citations = rag.prepare(org_id, req.message, history)
    conversation_id = conversation.id

    async def event_stream():
        if is_new:
            yield _sse("conversation", {"conversation_id": conversation_id})

        answer_parts: list[str] = []
        failed = False
        try:
            async for token in rag.llm.stream_chat(messages):
                answer_parts.append(token)
                yield _sse("token", {"text": token})
            yield _sse("sources", {"citations": [c.model_dump() for c in citations]})
            yield _sse("done", {})
        except Exception as e:  # surface errors to the client instead of hanging
            failed = True
            answer_parts.append(f"\n\n[error: {e}]")
            yield _sse("error", {"detail": str(e)})

        # A fresh session here (not the route-level `session` above) because
        # this generator body runs after the route has returned — the
        # request-scoped session may already be torn down by then. Persist the
        # assistant turn even on failure so a replayed conversation matches
        # what was seen live, rather than silently dropping the turn.
        async with SessionLocal() as write_session:
            write_session.add(
                Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content="".join(answer_parts),
                    citations_json=None if failed else [c.model_dump() for c in citations],
                    seq=base_seq + 1,
                )
            )
            write_conversation = await write_session.get(Conversation, conversation_id)
            write_conversation.updated_at = datetime.utcnow()
            await write_session.commit()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
