# Architecture

## Goal

Simple Thesis RAG is a local-first RAG pipeline for academic PDFs:

1. Parse PDF content with MinerU.
2. Enrich visuals (image/table/equation) with OpenAI descriptions.
3. Normalize to a typed Phase 1 -> Phase 2 contract.
4. Embed and upsert chunks into Qdrant.
5. Retrieve + generate answers.

## Runtime Module Map

- Entrypoints:
  - `main.py` (CLI launcher)
  - `app/ui/gradio_app.py` (Gradio UI)
- Shared runtime config + pipeline construction:
  - `src/utils/pipeline_factory.py`
  - `src/utils/config.py`
- Orchestration:
  - `src/pipelines/thesis_rag_pipeline.py`
- Phase 1 producer:
  - `src/ingestion/pdf_ingestor.py` (`MineruPhase1Producer`)
- Phase boundary contract:
  - `src/contracts/phase1_to_phase2.py`
- Phase 2 indexer/store:
  - `src/indexing/phase2_indexer.py` (`QdrantPhase2Indexer`)
  - `src/indexing/qdrant_store.py`
- Retrieval + generation:
  - `src/retrieval/retriever.py`
  - `src/generation/answer_generator.py`
- Shared source formatting:
  - `src/utils/source_formatting.py`

## End-to-End Data Flow

```mermaid
flowchart LR
    A[PDF input] --> B[Phase 1 Producer\nMinerU parse + metadata + visual descriptions]
    B --> C[Phase12Contract object\n(src/contracts/phase1_to_phase2.py)]
    C --> D[Phase 2 Indexer\ncontract -> qdrant payload chunks]
    D --> E[OpenAI Embeddings]
    E --> F[Qdrant collection]
    G[User query] --> H[Retriever\nembed query + vector search]
    F --> H
    H --> I[Answer Generator]
    I --> J[Final answer + sources]
```

## Phase Responsibilities

### Phase 1 (Parse + Enrich)

Input:

- `Phase1Request` with PDF path and ingest options.

Output:

- `Phase12Contract` object:
  - `document`
  - `assets[]`
  - `chunks[]`

Optional persisted snapshot:

- `data/processed/phase1_contract/v1/<document_id>.json`

### Phase 2 (Validate + Materialize + Index)

Input:

- `Phase12Contract`

Behavior:

- Validate schema and referential integrity.
- Convert to Qdrant payload chunk rows.
- Optional document replace (`delete_document(document_id)`).
- Embed `text` and upsert vectors + payload.

Output:

- `Phase2IngestResult` (`document_id`, `chunk_count`, `replaced_existing`, `contract_path`).

## Storage Layout

- Raw input PDFs:
  - `data/raw/<work_title>/<file>.pdf`
- MinerU parse outputs:
  - `data/interim/mineru_out/<document_id>/...`
- Visual description cache:
  - `data/processed/visual_descriptions/<document_id>.json`
- Phase contract snapshots:
  - `data/processed/phase1_contract/v1/<document_id>.json`
- Local Qdrant path mode (example):
  - `storage/vectorstore/qdrant`

## Runtime Defaults

Defaults come from `src/utils/config.py` and are reused by both CLI and UI through
`src/utils/pipeline_factory.py`.

Key defaults:

- `collection_name`: `thesis_chunks_v2`
- `embedding_model`: `text-embedding-3-small`
- `chat_model`: `gpt-4o-mini`
- `visual_description_model`: `gpt-4o-mini`
- `visual_types`: `image`, `table`, `equation`
- `describe_visuals_on_ingest`: `true`
- `replace_document_on_ingest`: `true`
- `persist_phase12_snapshot_on_ingest`: `true`

## OpenAI API Touchpoints

OpenAI is used in exactly three modules:

1. `src/embeddings/openai_embedder.py` (embeddings)
2. `src/generation/answer_generator.py` (final answer)
3. `src/ingestion/visual_describer.py` (visual descriptions)

`OPENAI_API_KEY` is required for ingest/query operations that call these modules.
