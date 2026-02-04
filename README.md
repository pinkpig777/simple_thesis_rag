# Simple Thesis RAG

## Overview

This project ingests thesis PDFs, stores chunk embeddings in Qdrant, and answers
questions with retrieval-augmented generation (RAG).

Primary entrypoints:

- `main.py`: CLI runner.
- `app/cli/main.py`: CLI argument parsing and command handlers.
- `src/pipelines/thesis_rag_pipeline.py`: Orchestration layer.

## Current Defaults

Default runtime settings (from `src/utils/config.py`):

- `collection_name`: `thesis_chunks_v2`
- `embedding_model`: `text-embedding-3-small`
- `embedding_dim`: `1536`
- `chat_model`: `gpt-4o-mini`
- `upsert_batch_size`: `100`
- Qdrant remote mode: `localhost:6333`
- Qdrant local mode: use `--qdrant-path <path>`

## Data Contract

Expected input layout:

```text
data/raw/<work_title>/<file>.pdf
```

Chunk text and metadata are stored in Qdrant payloads (including `payload["text"]`).

## Metadata Extraction Strategy

Metadata is path-aware and PDF-aware (`src/utils/metadata.py`):

- Uses folder name as canonical `work_title`.
- Infers `document_type` from filename (`manuscript`, `published`, `slides`, `readme`, `paper`).
- Uses PDF fields (`/Title`, `/Author`, `/Subject`, `/CreationDate`) when valid.
- Derives `year` from PDF creation date first, then fallback heuristics.
- Stores `source_path`, `source_folder`, and a path-based `document_id`.

Why path-based `document_id`:

- Prevents collisions across files with the same filename (for example many `Manuscript.pdf` files).

## OpenAI API Usage

OpenAI is used in two places:

1. Embeddings (`src/embeddings/openai_embedder.py`)
   - `client.embeddings.create(...)`
2. Answer generation (`src/generation/answer_generator.py`)
   - `client.chat.completions.create(...)`

`OPENAI_API_KEY` is required for `ingest`, `ingest-dir`, and `query`.
It is not required for `setup`.

## Pipeline Workflow

Ingestion workflow:

1. Read PDF file(s).
2. Extract page text.
3. Chunk text (word-based chunking).
4. Build metadata and `document_id`.
5. Call OpenAI embeddings API.
6. Upsert vectors + payload to Qdrant.

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

## Quickstart (Local Qdrant Mode)

1) Install dependencies:

```bash
uv sync
```

2) Create `.env`:

```bash
OPENAI_API_KEY=your_key_here
```

3) Setup local Qdrant collection:

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  setup
```

4) Ingest all PDFs in `data/raw/*/*.pdf`:

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  ingest-dir --dir ./data/raw --pattern '*/*.pdf'
```

5) Query:

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  query --question "what is household income"
```

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
