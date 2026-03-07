"""Formatting helpers for retrieved source display in CLI and UI."""

from __future__ import annotations

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
        document_id = str(metadata.get("document_id") or "Unknown")
        short_id = document_id[:8] if len(document_id) >= 8 else document_id
        page_number = metadata.get("page_number", "Unknown")
        score = float(source.get("score") or 0.0)

        lines.append(f"**[{rank}] {title}**")
        lines.append(f"- Score: `{score:.3f}` | Page: `{page_number}` | Doc: `{short_id}`")
        if filename:
            lines.append(f"- File: `{filename}`")
        if source_path:
            lines.append(f"- Path: `{source_path}`")
        lines.append("")

    return "\n".join(lines).strip()
