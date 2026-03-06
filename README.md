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

## Current Defaults

Default runtime settings (from `src/utils/config.py`):

- `collection_name`: `thesis_chunks_v2`
- `embedding_model`: `text-embedding-3-small`
- `embedding_dim`: `1536`
- `chat_model`: `gpt-4o-mini`
- `visual_description_model`: `gpt-4o-mini`
- `mineru_output_root`: `data/interim/mineru_out`
- `visual_description_root`: `data/processed/visual_descriptions`
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
5. Build metadata and `document_id`.
6. Delete existing points for `document_id` (replace mode).
7. Call OpenAI embeddings API.
8. Upsert vectors + payload to Qdrant.

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
