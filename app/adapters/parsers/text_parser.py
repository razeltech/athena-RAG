from app.core.parser import DocumentParser, ParsedDocument


class TextParser(DocumentParser):
    @property
    def extensions(self) -> list[str]:
        return [".txt", ".md", ".markdown"]

    def extract(self, path: str, source: str) -> ParsedDocument:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return ParsedDocument(text=f.read(), source=source)
