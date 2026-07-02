"""Dispatches a file to the right parser by extension.

TO ADD A NEW FORMAT (docx, pptx, xlsx, csv, pdf, ...):
  1. Create a parser class implementing DocumentParser (see text_parser.py).
  2. Register it below. Nothing else in the app changes.

Sequencing note (see docs/PLAN.md): start with easy text formats, add PDF last
(scans/tables/OCR are the hard part). Emails/SharePoint/Confluence/SQL are
CONNECTORS, not parsers — a separate, later effort.
"""
import os

from app.adapters.parsers.csv_parser import CsvParser
from app.adapters.parsers.docx_parser import DocxParser
from app.adapters.parsers.html_parser import HtmlParser
from app.adapters.parsers.pdf_parser import PdfParser
from app.adapters.parsers.text_parser import TextParser
from app.adapters.parsers.xlsx_parser import XlsxParser
from app.core.parser import DocumentParser, ParsedDocument


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, DocumentParser] = {}
        for parser in (
            TextParser(),
            HtmlParser(),
            DocxParser(),
            XlsxParser(),
            CsvParser(),
            PdfParser(),
        ):
            self.register(parser)

    def register(self, parser: DocumentParser) -> None:
        for ext in parser.extensions:
            self._parsers[ext.lower()] = parser

    def supported(self) -> list[str]:
        return sorted(self._parsers.keys())

    def parse(self, path: str, source: str) -> ParsedDocument:
        ext = os.path.splitext(source)[1].lower()
        parser = self._parsers.get(ext)
        if parser is None:
            raise ValueError(
                f"Unsupported file type '{ext}'. Supported: {self.supported()}"
            )
        return parser.extract(path, source)
