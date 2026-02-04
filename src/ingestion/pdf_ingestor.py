from pathlib import Path
from typing import Any

import PyPDF2

from src.chunking.text_chunker import chunk_text
from src.utils.metadata import build_document_id, extract_simple_metadata


def extract_pdf_chunks(
    pdf_path: Path,
    metadata: dict[str, Any] | None = None,
    chunk_size: int = 500,
) -> list[dict[str, Any]]:
    """Extract text from a PDF and return chunk payloads ready for indexing."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    document_metadata = dict(metadata) if metadata else extract_simple_metadata(pdf_path)
    document_metadata.setdefault("filename", pdf_path.name)
    document_metadata["document_id"] = build_document_id(pdf_path)

    all_chunks: list[dict[str, Any]] = []
    with pdf_path.open("rb") as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page_number, page in enumerate(pdf_reader.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                continue

            page_chunks = chunk_text(page_text, chunk_size=chunk_size)
            for chunk_index, chunk in enumerate(page_chunks):
                all_chunks.append(
                    {
                        **document_metadata,
                        "page_number": page_number,
                        "chunk_index": chunk_index,
                        "chunk_type": "text",
                        "text": chunk,
                        "char_count": len(chunk),
                    }
                )

    return all_chunks
