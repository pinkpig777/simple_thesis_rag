"""PDF ingestion pipeline backed by MinerU parsing and optional visual descriptions."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

from src.chunking.text_chunker import chunk_text
from src.ingestion.visual_describer import DEFAULT_VISUAL_TYPES, describe_visual_assets
from src.utils.metadata import build_document_id, extract_simple_metadata

DEFAULT_MINERU_OUTPUT_ROOT = Path("data/interim/mineru_out")
DEFAULT_VISUAL_DESCRIPTION_ROOT = Path("data/processed/visual_descriptions")


def _run_mineru(pdf_path: Path, output_dir: Path, backend: str = "pipeline") -> None:
    """Run MinerU CLI against a PDF and write parsed artifacts to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    command = ["mineru", "-p", str(pdf_path), "-o", str(output_dir), "-b", backend]
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


def _load_mineru_content_list(content_list_path: Path) -> list[dict[str, Any]]:
    """Load and normalize MinerU content list JSON rows."""
    raw_items = json.loads(content_list_path.read_text(encoding="utf-8"))
    return [item for item in raw_items if isinstance(item, dict)]


def _coerce_text(value: Any) -> str:
    """Normalize MinerU content fields to plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_coerce_text(item) for item in value]
        return " ".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        parts = [_coerce_text(item) for item in value.values()]
        return " ".join(part for part in parts if part).strip()
    return str(value).strip()


def _extract_page_texts(content_list: Sequence[dict[str, Any]]) -> tuple[dict[int, str], int]:
    """Aggregate MinerU content into page-level text blocks."""
    pages: dict[int, list[str]] = {}
    max_page = 0

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
            for key in ("table_caption", "table_body", "table_footnote"):
                text = _coerce_text(item.get(key))
                if text:
                    text_parts.append(text)
        elif item_type == "image":
            for key in ("image_caption", "img_caption", "image_footnote", "img_footnote"):
                text = _coerce_text(item.get(key))
                if text:
                    text_parts.append(text)

        if text_parts:
            pages.setdefault(page_number, []).extend(text_parts)

    page_texts = {page: "\n".join(parts).strip() for page, parts in pages.items() if parts}
    page_count = max_page if max_page > 0 else len(page_texts)
    return page_texts, page_count


def _format_visual_text(record: dict[str, Any]) -> str:
    """Build the embedding text body for one visual-description record."""
    description = str(record.get("description") or "").strip()
    item_type = str(record.get("item_type") or "visual").strip().lower()
    context = record.get("context") or {}

    lines = [f"{item_type.capitalize()} description", description]

    caption = _coerce_text(context.get("caption"))
    if caption:
        lines.append(f"Caption: {caption}")

    footnote = _coerce_text(context.get("footnote"))
    if footnote:
        lines.append(f"Footnote: {footnote}")

    table_body = _coerce_text(context.get("table_body_excerpt"))
    if table_body:
        lines.append(f"Table body excerpt: {table_body}")

    equation_latex = _coerce_text(context.get("equation_latex"))
    if equation_latex:
        lines.append(f"Equation (LaTeX): {equation_latex}")

    return "\n".join(line for line in lines if line).strip()


def _build_text_chunks(
    *,
    page_texts: dict[int, str],
    base_metadata: dict[str, Any],
    chunk_size: int,
) -> list[dict[str, Any]]:
    """Convert page texts into chunk payload records."""
    chunks: list[dict[str, Any]] = []
    for page_number in sorted(page_texts):
        page_text = (page_texts[page_number] or "").strip()
        if not page_text:
            continue

        page_chunks = chunk_text(page_text, chunk_size=chunk_size)
        for local_index, chunk in enumerate(page_chunks):
            chunks.append(
                {
                    **base_metadata,
                    "page_number": page_number,
                    "chunk_index": local_index,
                    "chunk_type": "text",
                    "text": chunk,
                    "char_count": len(chunk),
                }
            )
    return chunks


def _build_visual_chunks(
    *,
    visual_records: Sequence[dict[str, Any]],
    base_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert visual-description records into chunk payload records."""
    chunks: list[dict[str, Any]] = []
    sorted_records = sorted(
        visual_records,
        key=lambda item: (
            item.get("page_number") if isinstance(item.get("page_number"), int) else 0,
            item.get("item_index") if isinstance(item.get("item_index"), int) else 0,
        ),
    )

    for record in sorted_records:
        text = _format_visual_text(record)
        if not text:
            continue

        page_number = record.get("page_number")
        chunks.append(
            {
                **base_metadata,
                "page_number": page_number if isinstance(page_number, int) else None,
                "chunk_index": record.get("item_index"),
                "chunk_type": "visual_description",
                "visual_type": record.get("item_type"),
                "visual_item_index": record.get("item_index"),
                "image_rel_path": record.get("image_rel_path"),
                "image_path": record.get("image_path"),
                "description_model": record.get("description_model", ""),
                "described_at": record.get("described_at", ""),
                "text": text,
                "char_count": len(text),
            }
        )
    return chunks


def extract_pdf_chunks(
    pdf_path: Path,
    metadata: dict[str, Any] | None = None,
    chunk_size: int = 500,
    mineru_output_root: Path | str = DEFAULT_MINERU_OUTPUT_ROOT,
    describe_visuals: bool = True,
    visual_description_model: str = "gpt-4o-mini",
    visual_types: Sequence[str] = DEFAULT_VISUAL_TYPES,
    visual_description_root: Path | str = DEFAULT_VISUAL_DESCRIPTION_ROOT,
    overwrite_visual_descriptions: bool = False,
) -> list[dict[str, Any]]:
    """Extract text and optional visual descriptions, then return indexable chunks."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    document_id = build_document_id(pdf_path)
    mineru_root = Path(mineru_output_root)
    mineru_output_dir = (mineru_root / document_id).resolve()

    _run_mineru(pdf_path=pdf_path, output_dir=mineru_output_dir)
    content_list_path = _find_mineru_content_list(output_dir=mineru_output_dir, pdf_path=pdf_path)
    content_list = _load_mineru_content_list(content_list_path)

    page_texts, page_count = _extract_page_texts(content_list)
    auto_metadata = extract_simple_metadata(pdf_path, pdf_metadata=None)
    user_metadata = dict(metadata) if metadata else {}
    document_metadata = {**auto_metadata, **user_metadata}
    document_metadata.setdefault("filename", pdf_path.name)
    document_metadata.setdefault("page_count", page_count)
    document_metadata["document_id"] = document_id
    document_metadata["mineru_output_dir"] = str(mineru_output_dir)
    document_metadata["mineru_content_list_path"] = str(content_list_path.resolve())

    all_chunks = _build_text_chunks(
        page_texts=page_texts,
        base_metadata=document_metadata,
        chunk_size=chunk_size,
    )

    if describe_visuals:
        visual_output_path = Path(visual_description_root).resolve() / f"{document_id}.json"
        visual_payload = describe_visual_assets(
            input_path=content_list_path,
            output_path=visual_output_path,
            model=visual_description_model,
            allowed_types={item_type.strip().lower() for item_type in visual_types if item_type.strip()},
            overwrite=overwrite_visual_descriptions,
        )
        all_chunks.extend(
            _build_visual_chunks(
                visual_records=visual_payload.get("items", []),
                base_metadata=document_metadata,
            )
        )

    if not all_chunks:
        raise RuntimeError(f"No ingestible chunks extracted from {pdf_path}")

    return all_chunks
