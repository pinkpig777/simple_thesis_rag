# Simple RAG Project Scaffold

This structure is a solid default for most Retrieval-Augmented Generation (RAG) projects.

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

## Refactored entrypoints

- `main.py` -> CLI entrypoint
- `app/cli/main.py` -> command parser and command handlers
- `src/` -> modular RAG implementation (ingestion, indexing, retrieval, generation, pipeline)
- `thesis_rag.py` -> backward-compatible facade for older scripts

## Run with uv

```bash
# Install deps from pyproject.toml
uv sync

# Option A: run Qdrant server (Docker)
docker run -p 6333:6333 qdrant/qdrant

# Setup collection
uv run python main.py setup

# Ingest one PDF
uv run python main.py ingest --pdf ./theses/sample.pdf

# Ingest an entire directory
uv run python main.py ingest-dir --dir ./theses

# Query
uv run python main.py query --question "What are common machine learning optimization techniques?"
```

Or use embedded local mode (no Qdrant server):

```bash
uv run python main.py --qdrant-path ./storage/vectorstore/qdrant setup
```
