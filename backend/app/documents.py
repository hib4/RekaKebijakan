from __future__ import annotations

import re
import hashlib
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


def chunk_text(document_id: str, text: str, size: int = 1200, overlap: int = 150) -> list[dict]:
    if size < 100 or overlap < 0 or overlap >= size:
        raise ValueError("Konfigurasi chunk dokumen tidak valid")
    chunks = []
    start = 0
    while start < len(text):
        limit = min(len(text), start + size)
        end = limit
        if limit < len(text):
            boundary = text.rfind(" ", start + size // 2, limit)
            if boundary > start:
                end = boundary
        value = text[start:end].strip()
        if value:
            digest = hashlib.sha256(f"{document_id}:{len(chunks)}:{value}".encode()).hexdigest()
            chunks.append({
                "id": f"chunk_{digest[:16]}",
                "document_id": document_id,
                "ordinal": len(chunks),
                "text": value,
                "char_start": start,
                "char_end": end,
                "content_sha256": hashlib.sha256(value.encode()).hexdigest(),
                "metadata": {},
            })
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks
