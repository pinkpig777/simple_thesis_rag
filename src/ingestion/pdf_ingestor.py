import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.chunking.text_chunker import chunk_text
from src.utils.metadata import build_document_id, extract_simple_metadata


def _run_mineru(pdf_path: Path, output_dir: Path, backend: str = "pipeline") -> None:
    """Run MinerU CLI against a PDF and write parsed artifacts to output_dir."""
    command = [
        "mineru",
        "-p",
        str(pdf_path),
        "-o",
        str(output_dir),
        "-b",
        backend,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "MinerU CLI not found. Run `uv sync` to install dependencies and try again."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        details = stderr.splitlines()[-1] if stderr else "unknown MinerU error"
        raise RuntimeError(f"MinerU parsing failed for {pdf_path.name}: {details}") from exc


def _find_mineru_content_list(output_dir: Path, pdf_path: Path) -> Path:
    """Locate MinerU generated *_content_list.json output file for the PDF."""
    matches = list(output_dir.rglob(f"{pdf_path.stem}_content_list.json"))
    if not matches:
        matches = list(output_dir.rglob("*_content_list.json"))
    if not matches:
        raise RuntimeError(f"MinerU output not found for {pdf_path.name}.")
    return matches[0]


def _extract_page_texts_with_mineru(pdf_path: Path) -> tuple[dict[int, str], int]:
    """Parse PDF via MinerU and return extracted text keyed by 1-based page number."""
    with tempfile.TemporaryDirectory(prefix="mineru_") as temp_dir:
        output_dir = Path(temp_dir)
        _run_mineru(pdf_path=pdf_path, output_dir=output_dir)
        content_list_path = _find_mineru_content_list(output_dir=output_dir, pdf_path=pdf_path)
        content_list = json.loads(content_list_path.read_text(encoding="utf-8"))

    pages: dict[int, list[str]] = {}
    max_page = 0

    def _coerce_text(value: Any) -> str:
        """Normalize MinerU content fields to plain text."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return " ".join(_coerce_text(item) for item in value if _coerce_text(item)).strip()
        if isinstance(value, dict):
            return " ".join(
                _coerce_text(item) for item in value.values() if _coerce_text(item)
            ).strip()
        return str(value).strip()

    for item in content_list:
        page_idx = item.get("page_idx")
        if not isinstance(page_idx, int) or page_idx < 0:
            continue

        page_number = page_idx + 1
        max_page = max(max_page, page_number)

        item_type = item.get("type")
        text_parts: list[str] = []

        if item_type == "text":
            text = _coerce_text(item.get("text"))
            if text:
                text_parts.append(text)
        elif item_type == "equation":
            equation = _coerce_text(item.get("text"))
            if equation:
                text_parts.append(equation)
        elif item_type == "table":
            caption = _coerce_text(item.get("table_caption"))
            if caption:
                text_parts.append(caption)
            body = _coerce_text(item.get("table_body"))
            if body:
                text_parts.append(body)
            footnote = _coerce_text(item.get("table_footnote"))
            if footnote:
                text_parts.append(footnote)
        elif item_type == "image":
            caption = _coerce_text(item.get("img_caption"))
            if caption:
                text_parts.append(caption)
            footnote = _coerce_text(item.get("img_footnote"))
            if footnote:
                text_parts.append(footnote)

        if not text_parts:
            continue

        pages.setdefault(page_number, []).extend(text_parts)

    page_texts = {page: "\n".join(parts).strip() for page, parts in pages.items() if parts}
    page_count = max_page if max_page > 0 else len(page_texts)
    return page_texts, page_count


def extract_pdf_chunks(
    pdf_path: Path,
    metadata: dict[str, Any] | None = None,
    chunk_size: int = 500,
) -> list[dict[str, Any]]:
    """Extract text via MinerU and return chunk payloads ready for indexing."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    page_texts, page_count = _extract_page_texts_with_mineru(pdf_path)
    auto_metadata = extract_simple_metadata(pdf_path, pdf_metadata=None)
    user_metadata = dict(metadata) if metadata else {}
    document_metadata = {**auto_metadata, **user_metadata}
    document_metadata.setdefault("filename", pdf_path.name)
    document_metadata.setdefault("page_count", page_count)
    document_metadata["document_id"] = build_document_id(pdf_path)

    all_chunks: list[dict[str, Any]] = []
    for page_number in sorted(page_texts):
        page_text = (page_texts[page_number] or "").strip()
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
