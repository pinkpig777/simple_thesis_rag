# Design Decision Log

This document captures the key design decisions for the current `simple_rag` system.
It is a lightweight ADR-style log for implementation and maintenance alignment.

---

## DD-001: Modular RAG code structure

- **Status**: Accepted
- **Decision**: Split the original monolithic script into focused modules (`ingestion`, `chunking`, `embeddings`, `indexing`, `retrieval`, `generation`, `pipelines`, `utils`) with CLI entrypoints in `main.py` and `app/cli/main.py`.
- **Why**: Improve readability, testability, and iteration speed.
- **Consequence**: More files to navigate, but cleaner ownership boundaries.

## DD-002: Keep backward-compatible facade

- **Status**: Accepted
- **Decision**: Preserve `thesis_rag.py` as a facade around the refactored pipeline.
- **Why**: Avoid breaking older scripts/imports.
- **Consequence**: Minor duplication at the compatibility layer.

## DD-003: Use `uv` + `pyproject.toml` for dependency/runtime management

- **Status**: Accepted
- **Decision**: Standardize on `uv sync` and `uv run`.
- **Why**: Fast, reproducible environment setup.
- **Consequence**: Users should run commands with `uv` and usually `--env-file .env`.

## DD-004: Qdrant as vector database with two modes

- **Status**: Accepted
- **Decision**: Support remote Qdrant (`host`/`port`) and embedded local Qdrant (`--qdrant-path`).
- **Why**: Local development convenience plus production-ready server option.
- **Consequence**: Local mode is easiest to start; server mode required for full payload indexing behavior.

## DD-005: Default collection name is `thesis_chunks_v2`

- **Status**: Accepted
- **Decision**: Set default collection to `thesis_chunks_v2`.
- **Why**: Separate redesigned metadata/indexing from earlier collection state.
- **Consequence**: New users do not need to pass `--collection`; old collections may need migration/re-ingestion.

## DD-006: Idempotent collection setup

- **Status**: Accepted
- **Decision**: `setup` creates collection only when missing; ingestion commands also call setup automatically.
- **Why**: Reduce operational errors and command ordering friction.
- **Consequence**: Dedicated `setup` command is optional but still available.

## DD-007: Ensure payload indexes in server mode

- **Status**: Accepted
- **Decision**: Maintain payload indexes for key metadata fields (`document_id`, `year`, `university`, `author`, `work_title`, `document_type`, `chunk_type`, `page_number`) when not in local mode.
- **Why**: Improve metadata-filtered retrieval and operational consistency.
- **Consequence**: Extra setup calls in server mode; local mode skips index creation.

## DD-008: Use OpenAI for embeddings and answer generation

- **Status**: Accepted
- **Decision**: Use OpenAI embeddings (`text-embedding-3-small`) and chat generation (`gpt-4o-mini`).
- **Why**: Fast to implement, reliable quality.
- **Consequence**: `OPENAI_API_KEY` required for `ingest` and `query`.

## DD-009: Simple fixed-size chunking

- **Status**: Accepted
- **Decision**: Chunk by words with default size `500`.
- **Why**: Deterministic and cheap baseline.
- **Consequence**: Not semantic-aware; may split context imperfectly.

## DD-010: Store source text in Qdrant payload

- **Status**: Accepted
- **Decision**: Persist chunk text in `payload["text"]` alongside metadata.
- **Why**: Retrieval results can directly build generation context without re-opening PDFs.
- **Consequence**: Larger storage footprint in Qdrant.

## DD-011: Deterministic point IDs as UUIDv5

- **Status**: Accepted
- **Decision**: Point IDs are UUIDv5 of `document_id:chunk_index`.
- **Why**: Qdrant requires integer/UUID IDs and this keeps IDs stable.
- **Consequence**: ID format is opaque but deterministic.

## DD-012: Path-aware metadata strategy for dataset layout

- **Status**: Accepted
- **Decision**: Metadata extraction assumes `data/raw/<work_title>/<file>.pdf` and combines path-based cues with PDF embedded metadata (`/Title`, `/Author`, `/Subject`, `/CreationDate`).
- **Why**: Real dataset filenames like `Manuscript.pdf` need folder context for disambiguation.
- **Consequence**: Better source quality and less ambiguous citations.

## DD-013: Path-based `document_id`

- **Status**: Accepted
- **Decision**: Build `document_id` from normalized full PDF path hash, not filename only.
- **Why**: Avoid collisions across repeated filenames.
- **Consequence**: Moving files changes document IDs (requires re-ingest).

## DD-014: Retrieval strategy is dense semantic search + metadata filters

- **Status**: Accepted
- **Decision**: Use embedding similarity search with optional structured filters (`year`, `author`, `university`).
- **Why**: Keep baseline pipeline simple and robust.
- **Consequence**: Hybrid search/reranking is not currently enabled.

## DD-015: Qdrant client API compatibility handling

- **Status**: Accepted
- **Decision**: Support both new (`query_points`) and older (`search`) Qdrant client APIs.
- **Why**: Avoid runtime breakage across client versions.
- **Consequence**: Slightly more branching logic in index store adapter.

## DD-016: Answer style and citation behavior

- **Status**: Accepted
- **Decision**: Generated answer should not include inline citation markers (for example `(Manuscript, p.5)`), while CLI prints a separate source list.
- **Why**: Cleaner user-facing response and explicit source section.
- **Consequence**: Provenance is separated from prose answer body.

## DD-017: Preserve LaTeX in generated answers

- **Status**: Accepted
- **Decision**: Prompt generation to preserve math notation (for example `$...$` / `$$...$$`).
- **Why**: Thesis domain often contains equations and symbolic notation.
- **Consequence**: Answers may include LaTeX syntax that depends on renderer support.

## DD-018: Rich source line formatting in CLI

- **Status**: Accepted
- **Decision**: Source output includes disambiguating fields when available (title, source path, filename, short doc id, page, score).
- **Why**: Resolve ambiguity for generic files like `Manuscript.pdf`.
- **Consequence**: Longer source lines but clearer provenance.

## DD-019: Incremental commit workflow

- **Status**: Accepted
- **Decision**: Apply and commit changes incrementally per user request.
- **Why**: Traceability and safer rollback.
- **Consequence**: More, smaller commits in history.

## DD-020: Migrate PDF extraction from PyPDF2 to MinerU

- **Status**: Accepted
- **Decision**: Replace PyPDF2 page-text extraction with MinerU CLI parsing and ingest from MinerU `*_content_list.json`.
- **Why**: Better handling for academic PDFs with formulas, tables, and complex layouts.
- **Consequence**: Ingestion depends on MinerU runtime/model availability; PDF embedded metadata is no longer read directly via PyPDF2.

## DD-021: Build first UI as in-process Gradio app

- **Status**: Accepted
- **Decision**: Add `app/ui/gradio_app.py` as the first UI, directly invoking pipeline classes in the same Python process.
- **Why**: Fastest path to an interactive workflow without introducing API/service orchestration complexity.
- **Consequence**: Tight coupling between UI and pipeline runtime; later migration to API-backed UI is still possible.

---

## Open Decisions / Next Candidates

- Add hybrid search (dense + sparse) and/or reranker.
- Add automated migration utilities for legacy collections.
