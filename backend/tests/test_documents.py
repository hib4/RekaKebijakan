from pathlib import Path

import fitz
from docx import Document

from app.documents import chunk_text, extract_text


def test_extracts_txt_markdown_docx_and_pdf(tmp_path: Path):
    txt = tmp_path / "policy.txt"
    txt.write_text("Akses layanan publik", encoding="utf-8")
    markdown = tmp_path / "policy.md"
    markdown.write_text("# Kebijakan\nTransparansi", encoding="utf-8")
    docx = tmp_path / "policy.docx"
    document = Document()
    document.add_paragraph("Keadilan distribusi")
    document.save(docx)
    pdf = tmp_path / "policy.pdf"
    pdf_document = fitz.open()
    page = pdf_document.new_page()
    page.insert_text((72, 72), "Kesiapan infrastruktur")
    pdf_document.save(pdf)
    pdf_document.close()

    assert extract_text(txt) == "Akses layanan publik"
    assert "Transparansi" in extract_text(markdown)
    assert extract_text(docx) == "Keadilan distribusi"
    assert "Kesiapan infrastruktur" in extract_text(pdf)


def test_chunks_are_deterministic_and_preserve_offsets():
    text = " ".join(f"kata{i}" for i in range(100))
    first = chunk_text("doc-1", text, size=120, overlap=20)
    second = chunk_text("doc-1", text, size=120, overlap=20)
    assert first == second
    assert len(first) > 1
    assert all(chunk["char_start"] < chunk["char_end"] for chunk in first)
    assert all(len(chunk["content_sha256"]) == 64 for chunk in first)
