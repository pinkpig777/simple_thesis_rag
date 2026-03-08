# Simple Thesis RAG

Local-first RAG system for thesis PDFs with MinerU parsing, OpenAI enrichment, and Qdrant retrieval.

## What It Does

- Ingests PDF papers from `data/raw/*/*.pdf`
- Parses text/visual structure with MinerU
- Describes `image` / `table` / `equation` assets with OpenAI
- Builds a typed Phase 1 -> Phase 2 contract object
- Embeds chunks and stores vectors + metadata in Qdrant
- Answers questions with retrieval-augmented generation
- Returns inline citations in answer text using `[S#]` tags
- Validates citation tags against retrieved source count before returning answer
- Shows visual preview cards for cited image/table/equation evidence in UI
- Adds experimental local PDF page deep-links in source evidence

## Quickstart

1) Install dependencies

```bash
uv sync
```

2) Add API key in `.env`

```bash
OPENAI_API_KEY=your_key_here
```

3) Setup collection (local Qdrant path mode)

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  setup
```

4) Ingest all PDFs

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  ingest-dir --dir ./data/raw --pattern '*/*.pdf'
```

5) Query

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  query --question "what is household income"
```

## UI

Launch Gradio app:

```bash
uv run --env-file .env python app/ui/gradio_app.py
```

Recommended first run:

1. Configure settings.
2. Click **Setup Collection**.
3. Ingest one PDF (or ingest directory).
4. Run query and inspect cited evidence in the Sources and Visual Evidence panels.

Notes:

- Visual previews are shown as gallery cards with `[S#]`, type, and page.
- PDF page links are best-effort (`file://...#page=N`) and depend on your local viewer support.
- PDF page highlight is not implemented yet (planned next iteration).

## Core Entrypoints

- `main.py`: CLI launcher
- `app/cli/main.py`: CLI command handlers
- `app/ui/gradio_app.py`: Gradio UI
- `src/pipelines/thesis_rag_pipeline.py`: pipeline orchestrator

## Project Docs

- Architecture: `docs/architecture.md`
- Phase 1 -> Phase 2 contract: `docs/phase1_phase2_contract.md`
- Operations (setup, commands, troubleshooting): `docs/operations.md`
- Design decision log: `docs/design_decisions.md`

## Where Data Goes

- MinerU parse outputs: `data/interim/mineru_out/<document_id>/...`
- Visual description cache: `data/processed/visual_descriptions/<document_id>.json`
- Contract snapshots: `data/processed/phase1_contract/v1/<document_id>.json`
- Local vector store path: `storage/vectorstore/qdrant`

## OpenAI Usage

OpenAI API is used for:

- Embeddings: `src/embeddings/openai_embedder.py`
- Answer generation: `src/generation/answer_generator.py`
- Visual descriptions: `src/ingestion/visual_describer.py`

`OPENAI_API_KEY` is required for ingest/query operations.
