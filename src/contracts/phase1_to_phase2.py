"""Phase 1 to Phase 2 object contract, validation, and serialization helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol


PHASE12_SCHEMA_VERSION = "1.0"
CHUNK_TYPE_TEXT = "text"
CHUNK_TYPE_VISUAL_DESCRIPTION = "visual_description"
ALLOWED_CHUNK_TYPES = {CHUNK_TYPE_TEXT, CHUNK_TYPE_VISUAL_DESCRIPTION}
DEFAULT_VISUAL_TYPES = ("image", "table", "equation")


@dataclass(slots=True)
class Phase1Request:
    """Runtime request object passed to the Phase 1 producer."""

    pdf_path: Path
    metadata: dict[str, Any] | None = None
    chunk_size: int = 500
    describe_visuals: bool = True
    visual_types: tuple[str, ...] = DEFAULT_VISUAL_TYPES
    overwrite_visual_descriptions: bool = False


@dataclass(slots=True)
class Phase2IngestResult:
    """Runtime result object returned by the Phase 2 indexer."""

    document_id: str
    chunk_count: int
    replaced_existing: bool
    contract_path: str | None = None


@dataclass(slots=True)
class Phase12Document:
    """Document-level fields shared between Phase 1 and Phase 2."""

    document_id: str
    source_pdf_path: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize document object to contract dictionary form."""
        data = {
            "document_id": self.document_id,
            "source_pdf_path": self.source_pdf_path,
        }
        # Keep contract-reserved keys authoritative.
        for key, value in self.extra.items():
            if key in {"document_id", "source_pdf_path"}:
                continue
            data[key] = value
        return data

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Phase12Document":
        """Build document object from dictionary form."""
        document_id = str(value.get("document_id") or "")
        source_pdf_path = str(value.get("source_pdf_path") or "")
        extras = {
            key: item
            for key, item in value.items()
            if key not in {"document_id", "source_pdf_path"}
        }
        return cls(document_id=document_id, source_pdf_path=source_pdf_path, extra=extras)


@dataclass(slots=True)
class Phase12Asset:
    """Visual asset reference row for traceability and enrichment."""

    asset_id: str
    asset_type: str
    page_number: int | None = None
    content_list_path: str = ""
    item_index: int | None = None
    image_rel_path: str = ""
    image_path: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    description_model: str = ""
    described_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize asset object to contract dictionary form."""
        return {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "page_number": self.page_number,
            "content_list_path": self.content_list_path,
            "item_index": self.item_index,
            "image_rel_path": self.image_rel_path,
            "image_path": self.image_path,
            "context": self.context,
            "description": self.description,
            "description_model": self.description_model,
            "described_at": self.described_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Phase12Asset":
        """Build asset object from dictionary form."""
        return cls(
            asset_id=str(value.get("asset_id") or ""),
            asset_type=str(value.get("asset_type") or ""),
            page_number=value.get("page_number") if isinstance(value.get("page_number"), int) else None,
            content_list_path=str(value.get("content_list_path") or ""),
            item_index=value.get("item_index") if isinstance(value.get("item_index"), int) else None,
            image_rel_path=str(value.get("image_rel_path") or ""),
            image_path=str(value.get("image_path") or ""),
            context=dict(value.get("context") or {}),
            description=str(value.get("description") or ""),
            description_model=str(value.get("description_model") or ""),
            described_at=str(value.get("described_at") or ""),
        )


@dataclass(slots=True)
class Phase12Chunk:
    """Normalized chunk entry consumed by Phase 2 indexing."""

    chunk_id: str
    chunk_type: str
    text: str
    metadata: dict[str, Any]
    page_number: int | None = None
    chunk_index: int | None = None
    asset_id: str | None = None
    char_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize chunk object to contract dictionary form."""
        return {
            "chunk_id": self.chunk_id,
            "chunk_type": self.chunk_type,
            "text": self.text,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "asset_id": self.asset_id,
            "char_count": self.char_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Phase12Chunk":
        """Build chunk object from dictionary form."""
        return cls(
            chunk_id=str(value.get("chunk_id") or ""),
            chunk_type=str(value.get("chunk_type") or ""),
            text=str(value.get("text") or ""),
            metadata=dict(value.get("metadata") or {}),
            page_number=value.get("page_number") if isinstance(value.get("page_number"), int) else None,
            chunk_index=value.get("chunk_index") if isinstance(value.get("chunk_index"), int) else None,
            asset_id=(str(value.get("asset_id")) if value.get("asset_id") is not None else None),
            char_count=int(value.get("char_count") or len(str(value.get("text") or ""))),
        )


@dataclass(slots=True)
class Phase12Contract:
    """Canonical runtime object exchanged from Phase 1 to Phase 2."""

    document: Phase12Document
    chunks: list[Phase12Chunk]
    assets: list[Phase12Asset] = field(default_factory=list)
    schema_version: str = PHASE12_SCHEMA_VERSION
    generated_at: str = field(default_factory=lambda: utc_now_iso())
    producer: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the whole contract object to dictionary form."""
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "producer": dict(self.producer),
            "document": self.document.to_dict(),
            "assets": [asset.to_dict() for asset in self.assets],
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Phase12Contract":
        """Build contract object from dictionary form."""
        document = Phase12Document.from_dict(dict(value.get("document") or {}))
        assets = [
            Phase12Asset.from_dict(item)
            for item in value.get("assets", [])
            if isinstance(item, Mapping)
        ]
        chunks = [
            Phase12Chunk.from_dict(item)
            for item in value.get("chunks", [])
            if isinstance(item, Mapping)
        ]
        return cls(
            schema_version=str(value.get("schema_version") or ""),
            generated_at=str(value.get("generated_at") or ""),
            producer=dict(value.get("producer") or {}),
            document=document,
            assets=assets,
            chunks=chunks,
        )


class Phase1Producer(Protocol):
    """Runtime interface for any Phase 1 producer implementation."""

    def produce(self, request: Phase1Request) -> Phase12Contract:
        """Produce one normalized contract object from a Phase 1 request."""


class Phase2Indexer(Protocol):
    """Runtime interface for any Phase 2 indexer implementation."""

    def ingest(
        self,
        contract: Phase12Contract,
        *,
        replace_document: bool = True,
        contract_path: str | None = None,
    ) -> Phase2IngestResult:
        """Consume a contract object and index it in Phase 2 storage."""


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


def phase12_contract_to_dict(contract: Phase12Contract) -> dict[str, Any]:
    """Convert a contract object to dictionary form."""
    return contract.to_dict()


def phase12_contract_from_dict(data: Mapping[str, Any]) -> Phase12Contract:
    """Convert dictionary form to a typed contract object."""
    return Phase12Contract.from_dict(data)


def _as_contract_mapping(contract: Mapping[str, Any] | Phase12Contract) -> dict[str, Any]:
    """Normalize contract input to a mutable dictionary mapping."""
    if isinstance(contract, Phase12Contract):
        return phase12_contract_to_dict(contract)
    return dict(contract)


def validate_phase12_contract(contract: Mapping[str, Any] | Phase12Contract) -> None:
    """Validate required fields and referential integrity of a phase contract."""
    mapping = _as_contract_mapping(contract)

    required_top_level = {"schema_version", "generated_at", "producer", "document", "assets", "chunks"}
    missing = [key for key in required_top_level if key not in mapping]
    if missing:
        raise ValueError(f"Phase1->Phase2 contract missing keys: {missing}")

    if str(mapping["schema_version"]) != PHASE12_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported phase contract schema_version: "
            f"{mapping['schema_version']} (expected {PHASE12_SCHEMA_VERSION})"
        )

    document = mapping.get("document")
    if not isinstance(document, Mapping):
        raise ValueError("Contract field 'document' must be an object.")
    document_id = str(document.get("document_id") or "").strip()
    if not document_id:
        raise ValueError("Contract document.document_id is required.")
    source_pdf_path = str(document.get("source_pdf_path") or "").strip()
    if not source_pdf_path:
        raise ValueError("Contract document.source_pdf_path is required.")

    assets = mapping.get("assets")
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

    chunks = mapping.get("chunks")
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

        asset_id_value = chunk.get("asset_id")
        normalized_asset_id: str | None = None
        if asset_id_value is not None:
            normalized_asset_id = str(asset_id_value).strip()
            if not normalized_asset_id:
                raise ValueError(f"Chunk {chunk_id} has empty asset_id.")
            if normalized_asset_id not in asset_ids:
                raise ValueError(f"Chunk {chunk_id} references unknown asset_id: {normalized_asset_id}")

        if chunk_type == CHUNK_TYPE_VISUAL_DESCRIPTION and not normalized_asset_id:
            raise ValueError(f"Visual chunk {chunk_id} must reference a valid asset_id.")


def write_phase12_contract(
    contract: Mapping[str, Any] | Phase12Contract,
    output_path: Path,
) -> Path:
    """Validate and write a phase contract JSON file."""
    mapping = _as_contract_mapping(contract)
    validate_phase12_contract(mapping)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def load_phase12_contract(
    contract_path: Path,
    *,
    as_object: bool = False,
) -> dict[str, Any] | Phase12Contract:
    """Load and validate a phase contract JSON file."""
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Contract root must be object: {contract_path}")
    validate_phase12_contract(data)
    if as_object:
        return phase12_contract_from_dict(data)
    return data


def phase12_contract_to_qdrant_chunks(
    contract: Mapping[str, Any] | Phase12Contract,
) -> list[dict[str, Any]]:
    """Materialize Qdrant payload chunks from a validated phase contract."""
    mapping = _as_contract_mapping(contract)
    validate_phase12_contract(mapping)

    assets_by_id = {
        str(asset["asset_id"]): dict(asset)
        for asset in mapping["assets"]
        if isinstance(asset, Mapping) and asset.get("asset_id")
    }
    document = dict(mapping["document"])

    qdrant_chunks: list[dict[str, Any]] = []
    for chunk in mapping["chunks"]:
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
            "phase12_schema_version": mapping["schema_version"],
            "phase12_generated_at": mapping["generated_at"],
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
        payload.setdefault("source_pdf_path", document.get("source_pdf_path"))
        qdrant_chunks.append(payload)

    return qdrant_chunks


def persist_phase12_snapshot(
    contract: Phase12Contract,
    output_root: Path | str,
) -> Path:
    """Persist one contract object under output_root/<document_id>.json."""
    output_path = Path(output_root).resolve() / f"{contract.document.document_id}.json"
    return write_phase12_contract(contract, output_path)
