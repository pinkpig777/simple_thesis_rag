from dataclasses import dataclass


@dataclass(slots=True)
class RAGConfig:
    qdrant_path: str | None = None
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    collection_name: str = "thesis_chunks_v2"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    chat_model: str = "gpt-4o-mini"
    visual_description_model: str = "gpt-4o-mini"
    mineru_output_root: str = "data/interim/mineru_out"
    visual_description_root: str = "data/processed/visual_descriptions"
    describe_visuals_on_ingest: bool = True
    replace_document_on_ingest: bool = True
    upsert_batch_size: int = 100
