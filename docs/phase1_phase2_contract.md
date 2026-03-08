# Phase 1 -> Phase 2 Contract

## Purpose

This document defines the canonical data contract crossing the boundary between:

- Phase 1 producer (`Phase1Producer`)
- Phase 2 indexer (`Phase2Indexer`)

Contract module:

- `src/contracts/phase1_to_phase2.py`

Schema version:

- `1.0`

## Contract vs Interface

- Object contract (`Phase12Contract`): defines valid data shape.
- Module interface (`Phase1Producer`, `Phase2Indexer`): defines callable behavior.

In short:

- Contract answers: "what data is valid?"
- Interface answers: "who calls what?"

## Runtime Interface

```python
Phase1Producer.produce(request: Phase1Request) -> Phase12Contract
Phase2Indexer.ingest(contract: Phase12Contract, replace_document: bool) -> Phase2IngestResult
```

Current implementations:

- `src/ingestion/pdf_ingestor.py` -> `MineruPhase1Producer`
- `src/indexing/phase2_indexer.py` -> `QdrantPhase2Indexer`

## Top-Level Contract Shape

```json
{
  "schema_version": "1.0",
  "generated_at": "ISO-8601 UTC timestamp",
  "producer": {
    "name": "simple-rag",
    "phase": "phase1",
    "component": "src.ingestion.pdf_ingestor.MineruPhase1Producer"
  },
  "document": { "..." },
  "assets": ["..."],
  "chunks": ["..."]
}
```

## Required Fields

### `document`

Required:

- `document_id`
- `source_pdf_path`

Common optional fields copied into payload metadata:

- `title`, `work_title`, `document_type`, `author`, `authors`, `year`, `university`
- `filename`, `source_path`, `source_folder`, `dataset_split`, `page_count`
- `mineru_output_dir`, `mineru_content_list_path`

### `assets[]`

Each visual reference row may include:

- `asset_id` (required, unique)
- `asset_type` (`image` | `table` | `equation`)
- `page_number`
- `content_list_path`, `item_index`
- `image_rel_path`, `image_path`
- `context`
- `description`, `description_model`, `described_at`

`assets[]` may be empty when visual description is disabled.

### `chunks[]`

Each chunk must include:

- `chunk_id` (required, unique)
- `chunk_type` (`text` | `visual_description`)
- `text` (required, non-empty)
- `metadata` (required, must include matching `document_id`)

Common additional fields:

- `page_number`
- `chunk_index`
- `asset_id` (required for `visual_description`)
- `char_count`

## Validator Rules (Enforced)

`validate_phase12_contract(...)` enforces:

- Required top-level keys exist.
- `schema_version == "1.0"`.
- `document.document_id` and `document.source_pdf_path` are non-empty.
- `assets[].asset_id` values are unique.
- `chunks[]` is non-empty.
- `chunks[].chunk_id` values are unique.
- `chunks[].chunk_type` is valid.
- `chunks[].text` is non-empty.
- `chunks[].metadata.document_id == document.document_id`.
- `visual_description` chunks reference a valid `asset_id`.

## Materialization to Qdrant Payload

`phase12_contract_to_qdrant_chunks(...)` converts each contract chunk to a payload row.

Preserved fields:

- `chunk_id`, `chunk_type`, `text`, `page_number`, `chunk_index`, `char_count`, `asset_id`

Merged metadata:

- `metadata` fields are flattened into payload for filtering/retrieval.

Asset enrichment:

- For visual chunks: `visual_type`, `image_rel_path`, `image_path`, `visual_item_index`, `description_model`, `described_at`

Tracking fields:

- `phase12_schema_version`
- `phase12_generated_at`
- `phase12_contract_path` (set by Phase 2 when a snapshot path is available)

## Snapshot Location

When snapshot persistence is enabled:

- `data/processed/phase1_contract/v1/<document_id>.json`

## Template JSON

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-03-07T12:00:00Z",
  "producer": {
    "name": "simple-rag",
    "phase": "phase1",
    "component": "src.ingestion.pdf_ingestor.MineruPhase1Producer"
  },
  "document": {
    "document_id": "a3f8c2...content_hash...",
    "source_pdf_path": "/abs/path/data/raw/My Paper/Manuscript.pdf",
    "filename": "Manuscript.pdf",
    "title": "My Paper (manuscript)",
    "work_title": "My Paper",
    "document_type": "manuscript",
    "author": "Jane Doe",
    "year": 2024,
    "page_count": 42,
    "source_path": "data/raw/My Paper/Manuscript.pdf",
    "mineru_output_dir": "/abs/path/data/interim/mineru_out/a3f8c2...",
    "mineru_content_list_path": "/abs/path/data/interim/mineru_out/a3f8c2.../auto/Manuscript_content_list.json"
  },
  "assets": [
    {
      "asset_id": "asset_eq_001",
      "asset_type": "equation",
      "page_number": 11,
      "item_index": 132,
      "image_rel_path": "images/7cb9....jpg",
      "image_path": "/abs/path/data/interim/mineru_out/a3f8c2.../auto/images/7cb9....jpg",
      "context": {
        "equation_latex": "$$y = c + i$$"
      },
      "description": "Equation describing resource constraint.",
      "description_model": "gpt-4o-mini",
      "described_at": "2026-03-07T12:01:00Z"
    }
  ],
  "chunks": [
    {
      "chunk_id": "chunk_text_001",
      "chunk_type": "text",
      "text": "This section introduces the model assumptions...",
      "page_number": 3,
      "chunk_index": 0,
      "asset_id": null,
      "char_count": 58,
      "metadata": {
        "document_id": "a3f8c2...content_hash...",
        "title": "My Paper (manuscript)",
        "year": 2024
      }
    },
    {
      "chunk_id": "chunk_visual_001",
      "chunk_type": "visual_description",
      "text": "Equation description\nEquation describing resource constraint.",
      "page_number": 11,
      "chunk_index": 132,
      "asset_id": "asset_eq_001",
      "char_count": 64,
      "metadata": {
        "document_id": "a3f8c2...content_hash...",
        "title": "My Paper (manuscript)",
        "year": 2024,
        "visual_type": "equation",
        "image_rel_path": "images/7cb9....jpg"
      }
    }
  ]
}
```
