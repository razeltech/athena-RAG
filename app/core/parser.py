from abc import ABC, abstractmethod

from pydantic import BaseModel


class ParsedDocument(BaseModel):
    text: str
    source: str


class DocumentParser(ABC):
    @property
    @abstractmethod
    def extensions(self) -> list[str]:
        """File extensions this parser handles, e.g. ['.txt', '.md']."""
        ...

    @abstractmethod
    def extract(self, path: str, source: str) -> ParsedDocument:
        ...
