"""Phase 2 indexer that ingests normalized contract objects into Qdrant."""

from __future__ import annotations

from typing import Any

from src.contracts.phase1_to_phase2 import (
    Phase12Contract,
    Phase2Indexer,
    Phase2IngestResult,
    phase12_contract_to_qdrant_chunks,
)


class QdrantPhase2Indexer(Phase2Indexer):
    """Phase 2 module that consumes Phase 1 contract objects and indexes them."""

    def __init__(self, *, store: Any, embedder: Any, batch_size: int = 100) -> None:
        """Initialize Phase 2 dependencies for indexing contract chunks."""
        self.store = store
        self.embedder = embedder
        self.batch_size = batch_size

    def ingest(
        self,
        contract: Phase12Contract,
        *,
        replace_document: bool = True,
        contract_path: str | None = None,
    ) -> Phase2IngestResult:
        """Validate, materialize, and upsert one contract into Qdrant."""
        document_id = contract.document.document_id
        chunks = phase12_contract_to_qdrant_chunks(contract)
        if contract_path:
            for chunk in chunks:
                chunk["phase12_contract_path"] = contract_path

        if replace_document:
            self.store.delete_document(document_id)

        chunk_count = self.store.upsert_chunks(
            chunks,
            embedder=self.embedder,
            batch_size=self.batch_size,
        )
        return Phase2IngestResult(
            document_id=document_id,
            chunk_count=chunk_count,
            replaced_existing=replace_document,
            contract_path=contract_path,
        )
