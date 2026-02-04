from dataclasses import dataclass


@dataclass(slots=True)
class RAGConfig:
    qdrant_path: str | None = None
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    collection_name: str = "thesis_chunks"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    chat_model: str = "gpt-4o-mini"
    upsert_batch_size: int = 100
