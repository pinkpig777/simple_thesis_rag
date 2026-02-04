"""
Backward-compatible facade around the refactored RAG modules.
"""

from pathlib import Path
from typing import Any

from app.cli.main import main as cli_main
from src.chunking.text_chunker import chunk_text
from src.pipelines.thesis_rag_pipeline import ThesisRAGPipeline
from src.utils.config import RAGConfig
from src.utils.metadata import extract_simple_metadata


class ThesisRAG:
    def __init__(self, qdrant_host: str = "localhost", qdrant_port: int = 6333):
        """Initialize the compatibility facade with host/port Qdrant settings."""
        config = RAGConfig(qdrant_host=qdrant_host, qdrant_port=qdrant_port)
        self.pipeline = ThesisRAGPipeline(config=config)

        # Keep these attributes for compatibility with older scripts.
        self.qdrant = self.pipeline.store.client
        self.collection_name = self.pipeline.config.collection_name
        self.embedding_model = self.pipeline.config.embedding_model
        self.embedding_dim = self.pipeline.config.embedding_dim

    @property
    def openai(self):
        """Expose the underlying OpenAI client for compatibility."""
        return self.pipeline.embedder.client

    def setup_collection(self) -> bool:
        """Create the target Qdrant collection if it does not exist."""
        return self.pipeline.setup_collection()

    def embed_text(self, text: str) -> list[float]:
        """Generate an embedding for a single text string."""
        return self.pipeline.embedder.embed(text)

    def chunk_text(self, text: str, chunk_size: int = 500) -> list[str]:
        """Split text into fixed-size word chunks."""
        return chunk_text(text, chunk_size=chunk_size)

    def extract_simple_metadata(self, pdf_path: Path) -> dict[str, Any]:
        """Extract filename-derived metadata for a PDF."""
        return extract_simple_metadata(pdf_path)

    def ingest_pdf(
        self, pdf_path: Path, metadata: dict[str, Any] | None = None, chunk_size: int = 500
    ) -> int:
        """Ingest one PDF into the vector store and return chunk count."""
        return self.pipeline.ingest_pdf(pdf_path, metadata=metadata, chunk_size=chunk_size)

    def search(
        self, query: str, filters: dict[str, Any] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Retrieve top matching chunks for the query."""
        return self.pipeline.search(query=query, filters=filters, limit=limit)

    def generate_answer(
        self,
        query: str,
        context_chunks: list[dict[str, Any]],
        model: str = "gpt-4o-mini",
    ) -> str:
        """Generate an answer from already retrieved context chunks."""
        return self.pipeline.generate_answer(query=query, context_chunks=context_chunks, model=model)

    def query(
        self,
        question: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Run retrieval + generation for an end-to-end question answer."""
        return self.pipeline.query(question=question, filters=filters, top_k=top_k)


def main() -> int:
    """Run the CLI through the compatibility module."""
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
