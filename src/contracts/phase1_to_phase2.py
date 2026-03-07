"""Phase 1 to Phase 2 contract helpers for ingestion and indexing."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PHASE12_SCHEMA_VERSION = "1.0"
CHUNK_TYPE_TEXT = "text"
CHUNK_TYPE_VISUAL_DESCRIPTION = "visual_description"
ALLOWED_CHUNK_TYPES = {CHUNK_TYPE_TEXT, CHUNK_TYPE_VISUAL_DESCRIPTION}


def build_asset_id(
    *,
    document_id: str,
    asset_type: str,
    item_index: int | None,
    image_rel_path: str | None,
) -> str:
    """Build a deterministic asset id for one visual item."""
    raw = f"{document_id}:{asset_type}:{item_index}:{image_rel_path or ''}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def build_chunk_id(
    *,
    document_id: str,
    chunk_type: str,
    page_number: int | None,
    chunk_index: int | None,
    asset_id: str | None,
    text: str,
) -> str:
    """Build a deterministic chunk id for one normalized chunk."""
    text_digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    raw = f"{document_id}:{chunk_type}:{page_number}:{chunk_index}:{asset_id or ''}:{text_digest}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def validate_phase12_contract(contract: Mapping[str, Any]) -> None:
    """Validate required fields and referential integrity of a phase contract."""
    required_top_level = {"schema_version", "generated_at", "producer", "document", "assets", "chunks"}
    missing = [key for key in required_top_level if key not in contract]
    if missing:
        raise ValueError(f"Phase1->Phase2 contract missing keys: {missing}")

    if str(contract["schema_version"]) != PHASE12_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported phase contract schema_version: "
            f"{contract['schema_version']} (expected {PHASE12_SCHEMA_VERSION})"
        )

    document = contract.get("document")
    if not isinstance(document, Mapping):
        raise ValueError("Contract field 'document' must be an object.")
    document_id = str(document.get("document_id") or "").strip()
    if not document_id:
        raise ValueError("Contract document.document_id is required.")
    source_pdf_path = str(document.get("source_pdf_path") or "").strip()
    if not source_pdf_path:
        raise ValueError("Contract document.source_pdf_path is required.")

    assets = contract.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Contract field 'assets' must be a list.")
    asset_ids: set[str] = set()
    for asset in assets:
        if not isinstance(asset, Mapping):
            raise ValueError("Each asset must be an object.")
        asset_id = str(asset.get("asset_id") or "").strip()
        if not asset_id:
            raise ValueError("Each asset requires asset_id.")
        if asset_id in asset_ids:
            raise ValueError(f"Duplicate asset_id in contract: {asset_id}")
        asset_ids.add(asset_id)

    chunks = contract.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("Contract field 'chunks' must be a non-empty list.")

    chunk_ids: set[str] = set()
    for chunk in chunks:
        if not isinstance(chunk, Mapping):
            raise ValueError("Each chunk must be an object.")
        chunk_id = str(chunk.get("chunk_id") or "").strip()
        if not chunk_id:
            raise ValueError("Each chunk requires chunk_id.")
        if chunk_id in chunk_ids:
            raise ValueError(f"Duplicate chunk_id in contract: {chunk_id}")
        chunk_ids.add(chunk_id)

        chunk_type = str(chunk.get("chunk_type") or "").strip()
        if chunk_type not in ALLOWED_CHUNK_TYPES:
            raise ValueError(
                f"Invalid chunk_type '{chunk_type}'. Allowed values: {sorted(ALLOWED_CHUNK_TYPES)}"
            )

        text = str(chunk.get("text") or "").strip()
        if not text:
            raise ValueError(f"Chunk {chunk_id} has empty text.")

        metadata = chunk.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ValueError(f"Chunk {chunk_id} metadata must be an object.")
        metadata_document_id = str(metadata.get("document_id") or "").strip()
        if metadata_document_id != document_id:
            raise ValueError(
                f"Chunk {chunk_id} metadata.document_id mismatch: "
                f"{metadata_document_id} != {document_id}"
            )

        asset_id = chunk.get("asset_id")
        if asset_id is not None:
            asset_id = str(asset_id).strip()
            if not asset_id:
                raise ValueError(f"Chunk {chunk_id} has empty asset_id.")
            if asset_id not in asset_ids:
                raise ValueError(f"Chunk {chunk_id} references unknown asset_id: {asset_id}")

        if chunk_type == CHUNK_TYPE_VISUAL_DESCRIPTION and not asset_id:
            raise ValueError(f"Visual chunk {chunk_id} must reference a valid asset_id.")


def write_phase12_contract(contract: Mapping[str, Any], output_path: Path) -> Path:
    """Validate and write a phase contract JSON file."""
    validate_phase12_contract(contract)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def load_phase12_contract(contract_path: Path) -> dict[str, Any]:
    """Load and validate a phase contract JSON file."""
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Contract root must be object: {contract_path}")
    validate_phase12_contract(data)
    return data


def phase12_contract_to_qdrant_chunks(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Materialize Qdrant payload chunks from a validated phase contract."""
    validate_phase12_contract(contract)
    assets_by_id = {
        str(asset["asset_id"]): dict(asset)
        for asset in contract["assets"]
        if isinstance(asset, Mapping) and asset.get("asset_id")
    }
    document = dict(contract["document"])

    qdrant_chunks: list[dict[str, Any]] = []
    for chunk in contract["chunks"]:
        metadata = dict(chunk["metadata"])
        payload: dict[str, Any] = {
            **metadata,
            "chunk_id": chunk["chunk_id"],
            "chunk_type": chunk["chunk_type"],
            "text": chunk["text"],
            "page_number": chunk.get("page_number"),
            "chunk_index": chunk.get("chunk_index"),
            "char_count": chunk.get("char_count", len(str(chunk.get("text") or ""))),
            "asset_id": chunk.get("asset_id"),
            "phase12_schema_version": contract["schema_version"],
            "phase12_generated_at": contract["generated_at"],
        }

        asset_id = chunk.get("asset_id")
        if asset_id:
            asset = assets_by_id.get(str(asset_id), {})
            if asset:
                payload.setdefault("visual_type", asset.get("asset_type"))
                payload.setdefault("image_rel_path", asset.get("image_rel_path"))
                payload.setdefault("image_path", asset.get("image_path"))
                payload.setdefault("visual_item_index", asset.get("item_index"))
                payload.setdefault("description_model", asset.get("description_model"))
                payload.setdefault("described_at", asset.get("described_at"))

        payload.setdefault("document_id", document.get("document_id"))
        qdrant_chunks.append(payload)

    return qdrant_chunks

