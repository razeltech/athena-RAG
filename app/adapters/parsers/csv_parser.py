import csv

from app.core.parser import DocumentParser, ParsedDocument


class CsvParser(DocumentParser):
    @property
    def extensions(self) -> list[str]:
        return [".csv"]

    def extract(self, path: str, source: str) -> ParsedDocument:
        with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.reader(f)
            lines = [" | ".join(cell.strip() for cell in row) for row in reader if any(row)]
        return ParsedDocument(text="\n".join(lines), source=source)
