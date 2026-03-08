# Operations Guide

## Prerequisites

- Python managed by `uv`
- OpenAI API key
- Qdrant (local path mode or server mode)

Install dependencies:

```bash
uv sync
```

Create `.env`:

```bash
OPENAI_API_KEY=your_key_here
```

If MinerU model download is slow/blocked:

```bash
export MINERU_MODEL_SOURCE=modelscope
```

## Quick CLI Workflow

### 1) Setup collection

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  setup
```

### 2) Ingest all PDFs

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  ingest-dir --dir ./data/raw --pattern '*/*.pdf'
```

### 3) Ask a question

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  query --question "what is household income"
```

## UI Workflow (Gradio)

Launch UI:

```bash
uv run --env-file .env python app/ui/gradio_app.py
```

Recommended first-run path:

1. Confirm Settings values.
2. Click **Setup Collection**.
3. Ingest one PDF (or ingest directory).
4. Run queries in the Query tab.

## Default Runtime Settings

Source of truth: `src/utils/config.py`.

Important defaults:

- collection: `thesis_chunks_v2`
- embedding model: `text-embedding-3-small`
- chat model: `gpt-4o-mini`
- visual description model: `gpt-4o-mini`
- visual types: `image`, `table`, `equation`
- replace on ingest: enabled
- contract snapshot persistence: enabled

CLI and UI defaults are normalized via `src/utils/pipeline_factory.py`.

## Ingestion Outputs

For each ingested document:

- MinerU artifacts:
  - `data/interim/mineru_out/<document_id>/...`
- Visual description cache:
  - `data/processed/visual_descriptions/<document_id>.json`
- Contract snapshot:
  - `data/processed/phase1_contract/v1/<document_id>.json`
- Indexed chunk payloads + vectors:
  - Qdrant collection (local or server)

## Replace/Re-ingest Behavior

By default, ingest replaces existing records for the same `document_id`:

1. Delete old points where `document_id` matches.
2. Upsert current chunks.

This prevents duplicates for repeated uploads of the same PDF bytes.

## Standalone Visual Description Backfill

Use when you already have MinerU outputs and want to (re)generate descriptions:

```bash
uv run --env-file .env python scripts/describe_mineru_images.py \
  --input-path ./data/interim/mineru_out \
  --output-file ./data/processed/image_descriptions.json \
  --model gpt-4o-mini \
  --types image table equation
```

## Qdrant Modes

### Local path mode

- Use `--qdrant-path ./storage/vectorstore/qdrant`.
- No separate server process required.

### Server mode

Start Qdrant:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

Then run CLI without `--qdrant-path` (defaults to `localhost:6333`).

## Troubleshooting

### `Connection refused`

Cause:

- Qdrant server mode selected, but server not running.

Fix:

- Start Qdrant server, or switch to local path mode with `--qdrant-path`.

### `OPENAI_API_KEY` missing

Cause:

- Env var not loaded for commands needing OpenAI.

Fix:

- Use `uv run --env-file .env ...` and verify key name is exactly `OPENAI_API_KEY`.

### `MinerU CLI not found`

Cause:

- MinerU dependency not installed in environment.

Fix:

- Run `uv sync` and retry.

### Ingestion feels slow

Common reasons:

- MinerU parsing per PDF
- visual description API calls per image/table/equation

Mitigations:

- Reuse visual cache (do not overwrite unless needed).
- Test with a small subset first.
