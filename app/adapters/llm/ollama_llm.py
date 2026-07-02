"""Local LLM via Ollama. No API key, no cloud. To swap models, change
LLM_MODEL in .env (e.g. qwen2.5:14b-instruct-q4_K_M). To swap runtimes
(llama.cpp, vLLM), add a sibling adapter implementing LLMProvider."""
import json
from typing import AsyncIterator

import httpx

from app.config import settings
from app.core.llm import LLMProvider
from app.core.models import ChatMessage


class OllamaLLM(LLMProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.llm_model

    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {
                "temperature": settings.llm_temperature,
                "num_ctx": settings.llm_num_ctx,
            },
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("done"):
                        break
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
