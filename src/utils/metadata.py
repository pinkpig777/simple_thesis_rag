import hashlib
from pathlib import Path
from typing import Any


def build_document_id(pdf_path: Path) -> str:
    """Build a deterministic document ID from the PDF filename."""
    return hashlib.md5(pdf_path.name.encode("utf-8")).hexdigest()


def extract_simple_metadata(pdf_path: Path) -> dict[str, Any]:
    """
    Extract basic metadata from filename.
    Example filename format: 2024_MIT_JohnDoe_DeepLearning.pdf
    """
    filename_stem = pdf_path.stem
    parts = filename_stem.split("_")

    return {
        "filename": pdf_path.name,
        "year": int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 2024,
        "university": parts[1] if len(parts) > 1 else "Unknown",
        "author": parts[2] if len(parts) > 2 else "Unknown",
        "title": parts[3] if len(parts) > 3 else filename_stem,
    }
