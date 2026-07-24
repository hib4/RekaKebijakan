from pathlib import Path

import fitz
import pytest
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


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("fake.pdf", b"not a pdf"),
        ("fake.docx", b"PK\x03\x04not a valid office container"),
        ("binary.txt", b"\xff\xfe\x00\x01"),
        ("empty.md", b"  \n\t"),
    ],
)
def test_rejects_invalid_signatures_binary_text_and_empty_extraction(tmp_path: Path, name: str, content: bytes):
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(ValueError):
        extract_text(path)


def test_bounds_pdf_pages_extracted_characters_and_chunks(tmp_path: Path):
    pdf = tmp_path / "many.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Satu")
    document.new_page().insert_text((72, 72), "Dua")
    document.save(pdf)
    document.close()

    from app.documents import extract_document

    with pytest.raises(ValueError, match="halaman"):
        extract_document(pdf, max_pdf_pages=1)
    text = tmp_path / "long.txt"
    text.write_text("teks yang terlalu panjang", encoding="utf-8")
    with pytest.raises(ValueError, match="ekstraksi"):
        extract_document(text, max_chars=5)
    with pytest.raises(ValueError, match="potongan"):
        chunk_text("doc", " ".join(["kata"] * 100), size=100, overlap=10, max_chunks=1)
