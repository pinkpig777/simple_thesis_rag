from pathlib import Path
from typing import Any

from src.embeddings.openai_embedder import OpenAIEmbedder
from src.generation.answer_generator import AnswerGenerator
from src.indexing.qdrant_store import QdrantStore
from src.ingestion.pdf_ingestor import extract_pdf_chunks
from src.retrieval.retriever import Retriever
from src.utils.config import RAGConfig


class ThesisRAGPipeline:
    def __init__(self, config: RAGConfig | None = None) -> None:
        self.config = config or RAGConfig()
        self.openai_client = None
        self.embedder = OpenAIEmbedder(
            model=self.config.embedding_model,
            client=self.openai_client,
        )
        self.store = QdrantStore(
            qdrant_path=self.config.qdrant_path,
            host=self.config.qdrant_host,
            port=self.config.qdrant_port,
            collection_name=self.config.collection_name,
            embedding_dim=self.config.embedding_dim,
        )
        self.retriever = Retriever(store=self.store, embedder=self.embedder)
        self.answer_generator = AnswerGenerator(
            model=self.config.chat_model,
            client=self.openai_client,
        )

    def setup_collection(self) -> bool:
        return self.store.setup_collection()

    def ingest_pdf(
        self,
        pdf_path: Path,
        metadata: dict[str, Any] | None = None,
        chunk_size: int = 500,
    ) -> int:
        chunks = extract_pdf_chunks(pdf_path, metadata=metadata, chunk_size=chunk_size)
        return self.store.upsert_chunks(
            chunks,
            embedder=self.embedder,
            batch_size=self.config.upsert_batch_size,
        )

    def ingest_directory(self, directory: Path, pattern: str = "*.pdf") -> tuple[int, int]:
        pdf_files = sorted(directory.glob(pattern))
        total_chunks = 0
        for pdf_file in pdf_files:
            total_chunks += self.ingest_pdf(pdf_file)
        return len(pdf_files), total_chunks

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return self.retriever.search(query=query, filters=filters, limit=limit)

    def generate_answer(
        self, query: str, context_chunks: list[dict[str, Any]], model: str | None = None
    ) -> str:
        if model:
            self.answer_generator.model = model
        return self.answer_generator.generate(query=query, context_chunks=context_chunks)

    def query(
        self,
        question: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        sources = self.search(question, filters=filters, limit=top_k)
        answer = self.generate_answer(question, sources)
        return {"question": question, "answer": answer, "sources": sources}
