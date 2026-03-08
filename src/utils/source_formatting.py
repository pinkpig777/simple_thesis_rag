"""Formatting helpers for retrieved source display in CLI and UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence


GENERIC_TITLES = {"manuscript", "paper", "readme", "slides", "published", "unknown"}


def format_source_title(metadata: dict[str, Any]) -> str:
    """Return a readable title with work-level disambiguation when needed."""
    title = str(metadata.get("title") or "Unknown")
    work_title = str(metadata.get("work_title") or "")
    document_type = str(metadata.get("document_type") or "")

    normalized_title = title.strip().lower()
    if work_title and normalized_title in GENERIC_TITLES:
        return f"{work_title} ({document_type})" if document_type else work_title
    return title


def format_source_label(metadata: dict[str, Any]) -> str:
    """Return one-line source label for CLI output."""
    title = format_source_title(metadata)
    filename = str(metadata.get("filename") or "")
    source_path = str(metadata.get("source_path") or "")
    document_id = str(metadata.get("document_id") or "Unknown")
    short_id = document_id[:8] if len(document_id) >= 8 else document_id

    extras = [
        f"path: {source_path}" if source_path else "",
        f"file: {filename}" if filename else "",
        f"doc: {short_id}" if short_id else "",
    ]
    extras = [extra for extra in extras if extra]
    if not extras:
        return title
    return f"{title} | " + " | ".join(extras)


def _build_pdf_page_link(source_pdf_path: str, page_number: Any) -> str | None:
    """Build a local file URI with page anchor for PDF viewers that support it."""
    if not source_pdf_path:
        return None
    if not isinstance(page_number, int) or page_number < 1:
        return None
    try:
        file_uri = Path(source_pdf_path).resolve().as_uri()
    except ValueError:
        return None
    return f"{file_uri}#page={page_number}"


def format_sources_markdown(sources: Sequence[dict[str, Any]]) -> str:
    """Return a ranked markdown block for UI source rendering."""
    if not sources:
        return "No sources."

    lines = ["### Retrieved Sources", ""]
    for rank, source in enumerate(sources, start=1):
        metadata = source.get("metadata") or {}
        title = format_source_title(metadata)
        filename = str(metadata.get("filename") or "")
        source_path = str(metadata.get("source_path") or "")
        source_pdf_path = str(metadata.get("source_pdf_path") or "")
        document_id = str(metadata.get("document_id") or "Unknown")
        short_id = document_id[:8] if len(document_id) >= 8 else document_id
        page_number = metadata.get("page_number", "Unknown")
        chunk_type = str(source.get("chunk_type") or "text")
        visual_type = str(source.get("visual_type") or "")
        image_path = str(source.get("image_path") or "")
        preview = str(source.get("text") or "").strip().replace("\n", " ")
        preview = (preview[:260] + "...") if len(preview) > 260 else preview
        score = float(source.get("score") or 0.0)

        lines.append(f"**[S{rank}] {title}**")
        lines.append(
            f"- Score: `{score:.3f}` | Page: `{page_number}` | Doc: `{short_id}` | Type: `{chunk_type}`"
        )
        if visual_type:
            lines.append(f"- Visual type: `{visual_type}`")
        if filename:
            lines.append(f"- File: `{filename}`")
        if source_path:
            lines.append(f"- Path: `{source_path}`")
        if source_pdf_path:
            lines.append(f"- PDF: `{source_pdf_path}`")
            pdf_page_link = _build_pdf_page_link(source_pdf_path, page_number)
            if pdf_page_link:
                lines.append(f"- PDF page (experimental): [open page {page_number}]({pdf_page_link})")
        if image_path:
            lines.append(f"- Image: `{image_path}`")
        if preview:
            lines.append(f"- Evidence text: {preview}")
        lines.append("")

    return "\n".join(lines).strip()


def build_visual_preview_cards(sources: Sequence[dict[str, Any]]) -> list[tuple[str, str]]:
    """Build (image_path, caption) cards for cited visual evidence in the UI."""
    cards: list[tuple[str, str]] = []
    seen: set[str] = set()
    for rank, source in enumerate(sources, start=1):
        image_path = str(source.get("image_path") or "").strip()
        if not image_path or image_path in seen:
            continue
        if not Path(image_path).exists():
            continue
        metadata = source.get("metadata") or {}
        title = format_source_title(metadata)
        page_number = metadata.get("page_number", "Unknown")
        visual_type = str(source.get("visual_type") or "visual")
        caption = f"[S{rank}] {visual_type} | p.{page_number} | {title}"
        cards.append((image_path, caption))
        seen.add(image_path)
    return cards
