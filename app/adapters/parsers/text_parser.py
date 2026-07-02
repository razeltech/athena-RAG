from app.core.parser import DocumentParser, ParsedDocument


class TextParser(DocumentParser):
    """Plain UTF-8 text — covers prose formats and source code alike, since
    a .cs/.py/.js file is just text with no binary structure to extract."""

    @property
    def extensions(self) -> list[str]:
        return [
            ".txt", ".md", ".markdown",
            # source code, for asking questions about an ingested codebase
            ".cs", ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h",
            ".json", ".yaml", ".yml", ".shader",
        ]

    def extract(self, path: str, source: str) -> ParsedDocument:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return ParsedDocument(text=f.read(), source=source)
