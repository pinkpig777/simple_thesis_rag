# Simple Thesis RAG

```text
simple_rag/
├── app/                    # Entry points (API, CLI)
│   ├── api/
│   └── cli/
├── configs/                # YAML/TOML/JSON configs
├── data/                   # Local datasets
│   ├── raw/
│   ├── interim/
│   └── processed/
├── docs/                   # Design notes and runbooks
├── notebooks/              # Experiments and analysis
├── prompts/                # Prompt templates
├── scripts/                # One-off or scheduled scripts
├── src/                    # Core application code
│   ├── chunking/
│   ├── embeddings/
│   ├── evaluation/
│   ├── generation/
│   ├── indexing/
│   ├── ingestion/
│   ├── pipelines/
│   ├── retrieval/
│   └── utils/
├── storage/                # Local vector store + embeddings cache
│   ├── embeddings/
│   └── vectorstore/
└── tests/
    ├── e2e/
    ├── integration/
    └── unit/
```

## Entrypoints

- `main.py` -> CLI entrypoint
- `app/cli/main.py` -> command parser and command handlers
- `src/` -> modular RAG implementation (ingestion, indexing, retrieval, generation, pipeline)
- `thesis_rag.py` -> backward-compatible facade for older scripts

## Pipeline (Explicit)

Ingestion pipeline (`ingest` / `ingest-dir`):

1. Read PDFs from disk (`src/pipelines/thesis_rag_pipeline.py` -> `ingest_pdf` / `ingest_directory`).
2. Extract page text (`src/ingestion/pdf_ingestor.py`).
3. Chunk text into fixed-size word chunks (`src/chunking/text_chunker.py`).
4. Build metadata from folder path + PDF embedded fields, then create `document_id` (`src/utils/metadata.py`).
5. **[OpenAI API]** Generate embedding for each chunk (`src/embeddings/openai_embedder.py`).
6. Upsert chunk vectors + payload into Qdrant (`src/indexing/qdrant_store.py`).

Query pipeline (`query`):

1. **[OpenAI API]** Embed user question (`src/retrieval/retriever.py` -> `src/embeddings/openai_embedder.py`).
2. Run vector search in Qdrant with optional filters (`src/indexing/qdrant_store.py`).
3. Format top-k retrieved chunks with scores (`src/retrieval/retriever.py`).
4. Build LLM context from retrieved chunks (`src/generation/answer_generator.py`).
5. **[OpenAI API]** Generate final answer with citations (`src/generation/answer_generator.py`).

OpenAI API call sites:

- `src/embeddings/openai_embedder.py` -> `OpenAIEmbedder.embed()` uses `client.embeddings.create(...)`
- `src/generation/answer_generator.py` -> `AnswerGenerator.generate()` uses `client.chat.completions.create(...)`

Flow summary:

```text
PDFs -> extract text -> chunk -> embed -> Qdrant
Question -> embed -> Qdrant retrieve -> prompt with chunks -> answer
```

## Metadata Strategy

Metadata is now path-aware for your dataset layout: `data/raw/<work_title>/<file>.pdf`.

- `work_title`: parent folder name (canonical paper/work title)
- `document_type`: inferred from filename (`manuscript`, `published`, `slides`, `readme`, `paper`)
- `title`: built from PDF `/Title` when valid, otherwise from folder/filename + variant suffix
- `author` and `authors`: parsed from PDF `/Author`
- `year`: extracted from PDF creation date first, then filename/folder text
- `source_path` and `source_folder`: traceability back to file location
- `document_id`: hash of full PDF path (prevents collisions like multiple `Manuscript.pdf`)

## Run with uv

```bash
# Install deps from pyproject.toml
uv sync

# Put your key in .env:
# OPENAI_API_KEY=...
# (Needed for ingest/query, not required for setup)

# Option A: run Qdrant server
docker run -p 6333:6333 qdrant/qdrant

# Setup collection
uv run --env-file .env python main.py setup

# Ingest one PDF
uv run --env-file .env python main.py ingest --pdf ./theses/sample.pdf

# Ingest an entire directory
uv run --env-file .env python main.py ingest-dir --dir ./theses

# Query
uv run --env-file .env python main.py query --question "What are common machine learning optimization techniques?"
```

Or use embedded local Qdrant mode (no server process):

```bash
uv run --env-file .env python main.py --qdrant-path ./storage/vectorstore/qdrant setup
```

Ingest all PDFs under `data/raw/*/*.pdf`:

```bash
uv run --env-file .env python main.py \
  --qdrant-path ./storage/vectorstore/qdrant \
  ingest-dir --dir ./data/raw --pattern '*/*.pdf'
```
