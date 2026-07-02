from app.core.parser import DocumentParser, ParsedDocument


class PdfParser(DocumentParser):
    @property
    def extensions(self) -> list[str]:
        return [".pdf"]

    def extract(self, path: str, source: str) -> ParsedDocument:
        from pypdf import PdfReader

        reader = PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages).strip()
        if not text:
            raise ValueError(
                "No extractable text found — this may be a scanned PDF (OCR is not supported)."
            )
        return ParsedDocument(text=text, source=source)
