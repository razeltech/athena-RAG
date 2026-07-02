from app.core.parser import DocumentParser, ParsedDocument


class HtmlParser(DocumentParser):
    @property
    def extensions(self) -> list[str]:
        return [".html", ".htm"]

    def extract(self, path: str, source: str) -> ParsedDocument:
        from bs4 import BeautifulSoup

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return ParsedDocument(text=soup.get_text(separator="\n"), source=source)
