"""Shared helpers to build configured RAG pipelines from UI/CLI inputs."""

from __future__ import annotations

from typing import Any

from src.utils.config import RAGConfig


DEFAULT_CONFIG = RAGConfig()


def _normalize_optional_str(value: Any) -> str | None:
    """Normalize optional string-like input, returning None for empty values."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_str(value: Any, fallback: str) -> str:
    """Normalize a required string-like input with a fallback value."""
    normalized = _normalize_optional_str(value)
    return normalized if normalized is not None else fallback


def _normalize_int(value: Any, fallback: int) -> int:
    """Normalize int-like input with fallback for empty values."""
    if value is None:
        return fallback
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return fallback
    return int(float(text))


def build_config(
    *,
    qdrant_path: str | None = None,
    qdrant_host: str | None = None,
    qdrant_port: int | str | None = None,
    collection_name: str | None = None,
    embedding_model: str | None = None,
    chat_model: str | None = None,
    visual_description_model: str | None = None,
    mineru_output_root: str | None = None,
    visual_description_root: str | None = None,
    phase12_contract_root: str | None = None,
) -> RAGConfig:
    """Build a normalized runtime config from loosely typed UI/CLI values."""
    return RAGConfig(
        qdrant_path=_normalize_optional_str(qdrant_path),
        qdrant_host=_normalize_str(qdrant_host, DEFAULT_CONFIG.qdrant_host),
        qdrant_port=_normalize_int(qdrant_port, DEFAULT_CONFIG.qdrant_port),
        collection_name=_normalize_str(collection_name, DEFAULT_CONFIG.collection_name),
        embedding_model=_normalize_str(embedding_model, DEFAULT_CONFIG.embedding_model),
        chat_model=_normalize_str(chat_model, DEFAULT_CONFIG.chat_model),
        visual_description_model=_normalize_str(
            visual_description_model, DEFAULT_CONFIG.visual_description_model
        ),
        mineru_output_root=_normalize_str(mineru_output_root, DEFAULT_CONFIG.mineru_output_root),
        visual_description_root=_normalize_str(
            visual_description_root, DEFAULT_CONFIG.visual_description_root
        ),
        phase12_contract_root=_normalize_str(
            phase12_contract_root, DEFAULT_CONFIG.phase12_contract_root
        ),
    )


def build_pipeline(
    *,
    qdrant_path: str | None = None,
    qdrant_host: str | None = None,
    qdrant_port: int | str | None = None,
    collection_name: str | None = None,
    embedding_model: str | None = None,
    chat_model: str | None = None,
    visual_description_model: str | None = None,
    mineru_output_root: str | None = None,
    visual_description_root: str | None = None,
    phase12_contract_root: str | None = None,
):
    """Build a ThesisRAGPipeline using normalized config values."""
    from src.pipelines.thesis_rag_pipeline import ThesisRAGPipeline

    config = build_config(
        qdrant_path=qdrant_path,
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        collection_name=collection_name,
        embedding_model=embedding_model,
        chat_model=chat_model,
        visual_description_model=visual_description_model,
        mineru_output_root=mineru_output_root,
        visual_description_root=visual_description_root,
        phase12_contract_root=phase12_contract_root,
    )
    return ThesisRAGPipeline(config=config)
