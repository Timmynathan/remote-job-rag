from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader


def _extract_from_reader(reader: PdfReader) -> str:
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def extract_text(pdf_path: str | Path, *, reader: PdfReader | None = None) -> str:
    reader = reader or PdfReader(str(pdf_path))
    return _extract_from_reader(reader)


def extract_text_from_bytes(pdf_bytes: bytes, *, reader: PdfReader | None = None) -> str:
    reader = reader or PdfReader(io.BytesIO(pdf_bytes))
    return _extract_from_reader(reader)
