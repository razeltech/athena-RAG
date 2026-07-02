"""LLM provider seam. IMPORTANT: this is ALWAYS a local model (Ollama /
llama.cpp / vLLM). It is never a cloud API. Swapping models or runtimes must
require zero changes outside this adapter."""
from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.core.models import ChatMessage


class LLMProvider(ABC):
    @abstractmethod
    def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        """Yield answer tokens as they are generated."""
        raise NotImplementedError
