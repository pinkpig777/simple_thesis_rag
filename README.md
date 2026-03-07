# Simple Thesis RAG

## Overview

This project ingests thesis PDFs, stores chunk embeddings in Qdrant, and answers
questions with retrieval-augmented generation (RAG).

Primary entrypoints:

- `main.py`: CLI runner.
- `app/cli/main.py`: CLI argument parsing and command handlers.
- `src/pipelines/thesis_rag_pipeline.py`: Orchestration layer.
- `app/ui/gradio_app.py`: Gradio UI over the same in-process pipeline.

## New Features

- Upload-first ingestion flow in the UI.
- Automatic visual description for `image`, `table`, and `equation` during ingest.
- Document-level replace on ingest (delete old points for the same `document_id`, then upsert).
- Cached visual descriptions at `data/processed/visual_descriptions/<document_id>.json`.
- Canonical Phase 1 -> Phase 2 interface contract at `data/processed/phase1_contract/v1/<document_id>.json`.

## Current Defaults

Default runtime settings (from `src/utils/config.py`):

- `collection_name`: `thesis_chunks_v2`
- `embedding_model`: `text-embedding-3-small`
- `embedding_dim`: `1536`
- `chat_model`: `gpt-4o-mini`
- `visual_description_model`: `gpt-4o-mini`
- `mineru_output_root`: `data/interim/mineru_out`
- `visual_description_root`: `data/processed/visual_descriptions`
- `phase12_contract_root`: `data/processed/phase1_contract/v1`
- `describe_visuals_on_ingest`: `true`
- `replace_document_on_ingest`: `true`
- `upsert_batch_size`: `100`
- Qdrant remote mode: `localhost:6333`
- Qdrant local mode: use `--qdrant-path <path>`

## Data Contract

Expected input layout:

```text
data/raw/<work_title>/<file>.pdf
```

Chunk text and metadata are stored in Qdrant payloads (including `payload["text"]`).
Text extraction is performed by MinerU. Visual descriptions are cached to:

```text
data/processed/visual_descriptions/<document_id>.json
```

Phase 1 -> Phase 2 normalized contract is stored at:

```text
data/processed/phase1_contract/v1/<document_id>.json
```

## Metadata Extraction Strategy

Metadata is primarily path-aware (`src/utils/metadata.py`):

- Uses folder name as canonical `work_title`.
- Infers `document_type` from filename (`manuscript`, `published`, `slides`, `readme`, `paper`).
- Supports optional PDF metadata fields (`/Title`, `/Author`, `/Subject`, `/CreationDate`) when provided by an ingestion adapter.
- Derives `year` from PDF creation date first, then fallback heuristics.
- Stores `source_path`, `source_folder`, and a content-hash `document_id`.

Why content-hash `document_id`:

- Stable across UI upload temp paths (same PDF bytes map to same id).
- Enables document-level replace/upsert without duplicating the same uploaded file.

## OpenAI API Usage

OpenAI is used in three places:

1. Embeddings (`src/embeddings/openai_embedder.py`)
   - `client.embeddings.create(...)`
2. Answer generation (`src/generation/answer_generator.py`)
   - `client.chat.completions.create(...)`
3. Visual descriptions (`src/ingestion/visual_describer.py`)
   - `client.chat.completions.create(...)` with image input

`OPENAI_API_KEY` is required for `ingest`, `ingest-dir`, and `query`.
It is not required for `setup`.

## Pipeline Workflow

Ingestion workflow:

1. Read PDF file(s).
2. Run MinerU parse and persist artifacts under `data/interim/mineru_out/<document_id>/`.
3. Build text chunks from MinerU content.
4. Describe visual assets (`image`, `table`, `equation`) and build visual-description chunks.
5. Build and validate a Phase 1 -> Phase 2 contract JSON.
6. Persist contract to `data/processed/phase1_contract/v1/<document_id>.json`.
7. Phase 2 reads the contract and materializes Qdrant payload chunks.
8. Delete existing points for `document_id` (replace mode).
9. Call OpenAI embeddings API.
10. Upsert vectors + payload to Qdrant.

Query workflow:

1. Embed user question (OpenAI embeddings API).
2. Retrieve top-k chunks from Qdrant.
3. Build LLM context from retrieved chunks.
4. Generate final answer (OpenAI chat API).
5. Print answer and structured source list.

Generation behavior:

- The answer omits inline citation markers like `(Manuscript, p.5)`.
- LaTeX math notation is preserved when present.
- Sources are listed separately by CLI with title and disambiguation fields when available.

## Phase 1 -> Phase 2 Interface Contract (Detailed)

Contract module:

- `src/contracts/phase1_to_phase2.py`

Schema version:

- `1.0`

Primary purpose:

- Decouple parsing/enrichment (Phase 1) from indexing/storage (Phase 2) with one canonical JSON artifact per document.

### Contract File Location

```text
data/processed/phase1_contract/v1/<document_id>.json
```

### Top-Level Structure

```json
{
  "schema_version": "1.0",
  "generated_at": "ISO-8601 UTC timestamp",
  "producer": {
    "name": "simple-rag",
    "phase": "phase1",
    "component": "src.ingestion.pdf_ingestor"
  },
  "document": { "...doc-level metadata..." },
  "assets": [ "...visual assets..." ],
  "chunks": [ "...normalized ingest units..." ]
}
```

### `document` Object (Required Core Fields)

- `document_id` (required): stable content-hash document id.
- `source_pdf_path` (required): absolute path to the ingested PDF.
- Other metadata copied for retrieval/index filtering:
  - `title`, `work_title`, `document_type`, `author`, `authors`, `year`, `university`
  - `filename`, `source_path`, `source_folder`, `dataset_split`, `page_count`
  - `mineru_output_dir`, `mineru_content_list_path`

### `assets[]` (Visual Reference Layer)

Each asset row corresponds to one visual item (image/table/equation):

- `asset_id` (required, deterministic)
- `asset_type` (`image` | `table` | `equation`)
- `page_number`
- `content_list_path`, `item_index`
- `image_rel_path`, `image_path`
- `context`
- `description`, `description_model`, `described_at`

`assets[]` can be empty when visual description is disabled.

### `chunks[]` (Phase 2 Ingestion Units)

Each chunk must contain:

- `chunk_id` (required, deterministic)
- `chunk_type` (`text` | `visual_description`)
- `text` (required, non-empty)
- `page_number`
- `chunk_index`
- `asset_id` (required for `visual_description`, null for plain text)
- `char_count`
- `metadata` (required object; must contain matching `document_id`)

### Template JSON (Copy/Paste Starter)

Use this as a concrete contract template for tests, mocks, or integration docs:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-03-07T12:00:00Z",
  "producer": {
    "name": "simple-rag",
    "phase": "phase1",
    "component": "src.ingestion.pdf_ingestor"
  },
  "document": {
    "document_id": "a3f8c2...content_hash...",
    "source_pdf_path": "/abs/path/data/raw/My Paper/Manuscript.pdf",
    "filename": "Manuscript.pdf",
    "title": "My Paper (manuscript)",
    "work_title": "My Paper",
    "document_type": "manuscript",
    "author": "Jane Doe",
    "authors": ["Jane Doe", "John Doe"],
    "year": 2024,
    "university": "Unknown",
    "page_count": 42,
    "source_path": "data/raw/My Paper/Manuscript.pdf",
    "source_folder": "data/raw/My Paper",
    "dataset_split": "raw",
    "mineru_output_dir": "/abs/path/data/interim/mineru_out/a3f8c2...",
    "mineru_content_list_path": "/abs/path/data/interim/mineru_out/a3f8c2.../auto/Manuscript_content_list.json"
  },
  "assets": [
    {
      "asset_id": "asset_eq_001",
      "asset_type": "equation",
      "page_number": 11,
      "content_list_path": "/abs/path/data/interim/mineru_out/a3f8c2.../auto/Manuscript_content_list.json",
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
        "work_title": "My Paper",
        "document_type": "manuscript",
        "author": "Jane Doe",
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
        "work_title": "My Paper",
        "document_type": "manuscript",
        "author": "Jane Doe",
        "year": 2024,
        "visual_type": "equation",
        "image_rel_path": "images/7cb9....jpg",
        "image_path": "/abs/path/data/interim/mineru_out/a3f8c2.../auto/images/7cb9....jpg",
        "visual_item_index": 132,
        "description_model": "gpt-4o-mini",
        "described_at": "2026-03-07T12:01:00Z"
      }
    }
  ]
}
```

### Validation Rules Enforced

The contract validator enforces:

- Required top-level keys exist.
- `schema_version == "1.0"`.
- `document.document_id` and `document.source_pdf_path` are non-empty.
- `assets[].asset_id` values are unique.
- `chunks[]` is non-empty.
- `chunks[].chunk_id` values are unique.
- `chunks[].chunk_type` is one of `text` or `visual_description`.
- `chunks[].text` is non-empty.
- `chunks[].metadata.document_id` matches `document.document_id`.
- `visual_description` chunks must reference a valid `asset_id`.

### Phase 2 Materialization (Contract -> Qdrant Payload)

Phase 2 reads the contract and converts each `chunks[]` entry to a Qdrant payload:

- Keeps chunk core fields (`chunk_id`, `chunk_type`, `text`, `page_number`, `chunk_index`, `char_count`).
- Merges `metadata` into top-level payload (to preserve current query code path).
- Enriches visual chunks from `assets[]` when available (`visual_type`, `image_path`, etc.).
- Adds contract tracking fields:
  - `phase12_schema_version`
  - `phase12_generated_at`
  - `phase12_contract_path`

### Why This Boundary Matters

- Clear ownership: Phase 1 writes canonical data; Phase 2 only consumes canonical data.
- Easier replay/debug: inspect one contract file to understand exactly what is indexed.
- Safer evolution: new fields can be added without breaking existing ingestion consumers.

## Visual Description Script (Standalone / Backfill)

Main ingestion already performs visual descriptions automatically.  
Use this script when you want standalone generation/backfill from existing MinerU output.

Example:

```bash
uv run --env-file .env python scripts/describe_mineru_images.py \
  --input-path ./data/interim/mineru_out \
  --output-file ./data/processed/image_descriptions.json \
  --model gpt-4o-mini \
  --types image table equation
```

Output JSON includes, for each described asset:

- `id` (stable record id)
- `content_list_path` + `item_index` (exact MinerU item reference)
- `image_rel_path` + `image_path` (file reference)
- `page_number`, `item_type`, `context`, `description`

Use `--dry-run` to preview discovered items without calling OpenAI.
If `--types` is omitted, the script processes `image`, `table`, and `equation`.

## Quickstart (Local Qdrant Mode)

0) Clone this project
```bash
git clone https://github.com/pinkpig777/simple_thesis_rag.git
cd simple_thesis_rag
```

1) Install `uv`

```bash
# On macOS and Linux.
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2) Install dependencies:

```bash
uv sync
```

If MinerU model download is slow/blocked in your region, set:

```bash
export MINERU_MODEL_SOURCE=modelscope
```

3) Create `.env` (copy the `.env.example` and rename it):

```bash
OPENAI_API_KEY=your_key_here
```

4) Setup local Qdrant collection:

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  setup
```

5) Ingest all PDFs in `data/raw/*/*.pdf`:

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  --mineru-output-root ./data/interim/mineru_out \
  --visual-description-root ./data/processed/visual_descriptions \
  --phase12-contract-root ./data/processed/phase1_contract/v1 \
  ingest-dir --dir ./data/raw --pattern '*/*.pdf'
```

6) Query:

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  query --question "what is household income"
```

## Gradio UI (No Separate Backend Service)

Launch interactive UI with the same pipeline code (no FastAPI required):

```bash
uv run --env-file .env python app/ui/gradio_app.py
```

In the UI:

- Use **Settings** to pick local path/host/collection/model values and MinerU/cache roots.
- Use **Ingest** tab to upload one PDF or ingest a folder.
- Keep **Describe visuals** and **Replace existing document** enabled for upload-first workflow.
- Use **Query** tab for answer generation and source inspection.

## App Usage (Step-by-Step)

1) Launch app:

```bash
uv run --env-file .env python app/ui/gradio_app.py
```

2) In **Settings**:

- Set `Qdrant Local Path` to `./storage/vectorstore/qdrant` (or use host/port mode).
- Confirm `Collection` (default: `thesis_chunks_v2`).
- Confirm model settings (`Embedding`, `Chat`, `Visual Description`).
- Confirm:
  - `MinerU Output Root` (default: `./data/interim/mineru_out`)
  - `Visual Description Cache Root` (default: `./data/processed/visual_descriptions`)
  - `Phase1->Phase2 Contract Root` (default: `./data/processed/phase1_contract/v1`)

3) Click **Setup Collection** once.

4) In **Ingest** tab:

- Upload one PDF in **Upload PDF** (or provide a path in `PDF Path (fallback)`).
- Keep these checked for the intended workflow:
  - **Describe visuals (image/table/equation)**
  - **Replace existing document in collection**
- Click **Ingest PDF** and wait for completion status.

5) In **Query** tab:

- Ask a question, set `Top K`, and optional metadata filters.
- Review the generated answer and retrieved source list.

6) Optional directory ingest:

- Use **Ingest Directory** with a glob pattern (default `*/*.pdf`) for batch indexing.

## Server Mode (Optional)

Start Qdrant:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

Then run CLI commands without `--qdrant-path`.

## Note on Existing Collections

If your current collection was built before metadata redesign, source lines may still
show generic names (for example `Manuscript`). The default collection is now
`thesis_chunks_v2`, so you can re-ingest without passing `--collection`:

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  setup

uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  ingest-dir --dir ./data/raw --pattern '*/*.pdf'
```
