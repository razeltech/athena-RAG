"""Domain models shared across layers."""
from pydantic import BaseModel


class Chunk(BaseModel):
    id: str
    doc_id: str
    org_id: str
    source: str
    chunk_index: int
    text: str


class Citation(BaseModel):
    n: int
    doc_id: str
    source: str
    chunk_index: int
    snippet: str


class ChatMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str
