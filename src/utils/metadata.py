import hashlib
import re
from pathlib import Path
from typing import Any, Mapping


def build_document_id(pdf_path: Path) -> str:
    """Build a deterministic document ID from PDF bytes, with path fallback."""
    digest = hashlib.md5()
    try:
        with pdf_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        normalized_path = pdf_path.as_posix().strip().lower()
        return hashlib.md5(normalized_path.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    """Collapse repeated whitespace and trim surrounding spaces."""
    return re.sub(r"\s+", " ", text).strip()


def _clean_pdf_value(value: Any) -> str | None:
    """Convert raw PDF metadata values into clean strings when possible."""
    if value is None:
        return None

    text = _normalize_text(str(value))
    if not text:
        return None
    if text.startswith("IndirectObject("):
        return None
    return text


def _extract_year(text: str | None) -> int | None:
    """Extract a plausible year from text."""
    if not text:
        return None

    match = re.search(r"(19|20)\d{2}", text)
    if not match:
        return None

    year = int(match.group(0))
    return year if 1900 <= year <= 2100 else None


def _split_authors(raw_author: str | None) -> list[str]:
    """Split author metadata into a cleaned list of names."""
    if not raw_author:
        return []

    normalized = raw_author.replace(" and ", ",")
    parts = re.split(r"[;,]", normalized)
    authors = [_normalize_text(part) for part in parts if _normalize_text(part)]
    return authors


def _infer_document_type(file_stem: str) -> str:
    """Infer document type from filename conventions."""
    lowered = file_stem.lower()
    if "slide" in lowered:
        return "slides"
    if "readme" in lowered:
        return "readme"
    if "manuscript" in lowered:
        return "manuscript"
    if "publish" in lowered:
        return "published"
    if "appendix" in lowered:
        return "appendix"
    return "paper"


def _filename_is_generic(file_stem: str) -> bool:
    """Return True when the filename stem is a generic variant label."""
    lowered = file_stem.lower().strip()
    generic_terms = {
        "manuscript",
        "paper",
        "readme",
        "slides",
        "slide",
        "published",
        "draft",
        "preprint",
    }
    return lowered in generic_terms


def _build_title(
    work_title: str,
    file_stem: str,
    pdf_title: str | None,
    document_type: str,
) -> str:
    """Build a display title using PDF metadata and path-level context."""
    filename_title = _normalize_text(file_stem.replace("_", " "))
    base_title = pdf_title or (work_title if _filename_is_generic(file_stem) else filename_title)

    suffix_map = {
        "manuscript": "manuscript",
        "published": "published",
        "slides": "slides",
        "readme": "readme",
    }
    suffix = suffix_map.get(document_type)
    if suffix and suffix not in base_title.lower():
        return f"{base_title} ({suffix})"
    return base_title


def extract_simple_metadata(
    pdf_path: Path, pdf_metadata: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """
    Extract richer metadata using path conventions and embedded PDF metadata.

    Path-aware strategy for this dataset:
    - `data/raw/<work_title>/<file>.pdf`
    - folder name provides canonical work title
    - filename provides variant hints (manuscript, slides, published, readme)
    """
    work_title = _normalize_text(pdf_path.parent.name.replace("_", " "))
    document_type = _infer_document_type(pdf_path.stem)

    pdf_title = _clean_pdf_value((pdf_metadata or {}).get("/Title"))
    pdf_author = _clean_pdf_value((pdf_metadata or {}).get("/Author"))
    pdf_subject = _clean_pdf_value((pdf_metadata or {}).get("/Subject"))
    creation_date = _clean_pdf_value((pdf_metadata or {}).get("/CreationDate"))
    authors = _split_authors(pdf_author)

    year = (
        _extract_year(creation_date)
        or _extract_year(pdf_path.stem)
        or _extract_year(work_title)
        or 0
    )

    title = _build_title(
        work_title=work_title,
        file_stem=pdf_path.stem,
        pdf_title=pdf_title,
        document_type=document_type,
    )

    source_path = pdf_path.as_posix()
    source_folder = pdf_path.parent.as_posix()
    parent_folder = pdf_path.parent.parent.name if pdf_path.parent.parent != pdf_path.parent else ""

    if parent_folder and parent_folder.lower() == "raw":
        dataset_split = "raw"
    else:
        dataset_split = parent_folder or "unknown"

    return {
        "filename": pdf_path.name,
        "source_path": source_path,
        "source_folder": source_folder,
        "dataset_split": dataset_split,
        "work_title": work_title,
        "document_type": document_type,
        "title": title,
        "author": authors[0] if authors else "Unknown",
        "authors": authors,
        "year": year,
        "university": "Unknown",
        "pdf_title": pdf_title or "",
        "pdf_subject": pdf_subject or "",
        "pdf_creation_date": creation_date or "",
        "has_pdf_metadata": bool(pdf_title or pdf_author or pdf_subject or creation_date),
    }
