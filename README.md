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
