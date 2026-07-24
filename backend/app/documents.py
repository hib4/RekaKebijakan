from __future__ import annotations

import re
from pathlib import Path

import fitz
from docx import Document


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Format berkas tidak didukung: {suffix or 'tanpa ekstensi'}")
    if suffix == ".pdf":
        with fitz.open(path) as document:
            text = "\n".join(page.get_text() for page in document)
    elif suffix == ".docx":
        text = "\n".join(paragraph.text for paragraph in Document(path).paragraphs)
    else:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    return re.sub(r"\s+", " ", text).strip()
