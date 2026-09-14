from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extract_text(pdf_path: str | Path, *, reader: PdfReader | None = None) -> str:
    reader = reader or PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
