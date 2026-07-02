from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org, get_db_session
from app.db.models import Conversation, Message

router = APIRouter()


@router.get("/conversations")
async def list_conversations(
    org_id: str = Depends(get_current_org),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.org_id == org_id)
        .order_by(Conversation.updated_at.desc())
    )
    return [
        {
            "id": c.id,
            "title": c.title,
            "persona": c.persona,
            "mode": c.mode,
            "updated_at": c.updated_at.isoformat(),
        }
        for c in result.scalars().all()
    ]


async def _get_owned_conversation(
    conversation_id: str, org_id: str, session: AsyncSession
) -> Conversation:
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.org_id == org_id
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        # 404, not 403 — don't leak whether another org's conversation exists.
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    org_id: str = Depends(get_current_org),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    await _get_owned_conversation(conversation_id, org_id, session)
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.seq)
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "citations": m.citations_json,
            "created_at": m.created_at.isoformat(),
        }
        for m in result.scalars().all()
    ]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    org_id: str = Depends(get_current_org),
    session: AsyncSession = Depends(get_db_session),
):
    conversation = await _get_owned_conversation(conversation_id, org_id, session)
    result = await session.execute(
        select(Message).where(Message.conversation_id == conversation_id)
    )
    for message in result.scalars().all():
        await session.delete(message)
    await session.delete(conversation)
    await session.commit()
    return {"deleted": conversation_id}
