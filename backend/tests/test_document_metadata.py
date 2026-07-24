from pathlib import Path

import fitz

from app.documents import ExtractedDocument, chunk_text, extract_document, extract_text


def test_text_extraction_preserves_lines_and_paragraphs_with_legacy_string_api(tmp_path: Path):
    path = tmp_path / "policy.txt"
    path.write_text("Baris pertama\n\nBaris kedua", encoding="utf-8")

    extracted = extract_document(path)
    legacy = extract_text(path)

    assert isinstance(extracted, ExtractedDocument)
    assert legacy == "Baris pertama Baris kedua"
    assert isinstance(legacy, str)
    assert [(item.paragraph, item.line) for item in extracted.segments] == [(1, 1), (2, 3)]
    assert all(extracted.text[item.char_start:item.char_end] == item.text for item in extracted.segments)

    chunks = chunk_text("doc-1", legacy, size=100, overlap=10)
    assert chunks[0]["metadata"]["paragraphs"] == [1, 2]
    assert [item["line"] for item in chunks[0]["metadata"]["lines"]] == [1, 3]


def test_pdf_extraction_preserves_page_metadata(tmp_path: Path):
    path = tmp_path / "policy.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Halaman satu")
    document.new_page().insert_text((72, 72), "Halaman dua")
    document.save(path)
    document.close()

    extracted = extract_document(path)
    chunks = chunk_text("doc-pdf", extracted, size=100, overlap=10)

    assert [segment.page for segment in extracted.segments] == [1, 2]
    assert chunks[0]["metadata"]["pages"] == [1, 2]
