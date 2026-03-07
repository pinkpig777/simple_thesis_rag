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
        """Wire all core components for ingestion, retrieval, and generation."""
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
        """Ensure the configured collection exists in Qdrant."""
        return self.store.setup_collection()

    def ingest_pdf(
        self,
        pdf_path: Path,
        metadata: dict[str, Any] | None = None,
        chunk_size: int = 500,
        describe_visuals: bool | None = None,
        replace_document: bool | None = None,
        overwrite_visual_descriptions: bool = False,
    ) -> int:
        """Extract, (optionally) describe visuals, and upsert chunks for one PDF."""
        use_describe_visuals = (
            self.config.describe_visuals_on_ingest
            if describe_visuals is None
            else describe_visuals
        )
        use_replace_document = (
            self.config.replace_document_on_ingest
            if replace_document is None
            else replace_document
        )

        chunks = extract_pdf_chunks(
            pdf_path,
            metadata=metadata,
            chunk_size=chunk_size,
            mineru_output_root=self.config.mineru_output_root,
            describe_visuals=use_describe_visuals,
            visual_description_model=self.config.visual_description_model,
            visual_description_root=self.config.visual_description_root,
            overwrite_visual_descriptions=overwrite_visual_descriptions,
            phase12_contract_root=self.config.phase12_contract_root,
        )
        if use_replace_document and chunks:
            self.store.delete_document(chunks[0]["document_id"])

        return self.store.upsert_chunks(
            chunks,
            embedder=self.embedder,
            batch_size=self.config.upsert_batch_size,
        )

    def ingest_directory(
        self,
        directory: Path,
        pattern: str = "*.pdf",
        describe_visuals: bool | None = None,
        replace_document: bool | None = None,
        overwrite_visual_descriptions: bool = False,
    ) -> tuple[int, int]:
        """Ingest all matching PDFs in a directory tree and return totals."""
        pdf_files = sorted(directory.glob(pattern))
        total_chunks = 0
        for pdf_file in pdf_files:
            total_chunks += self.ingest_pdf(
                pdf_file,
                describe_visuals=describe_visuals,
                replace_document=replace_document,
                overwrite_visual_descriptions=overwrite_visual_descriptions,
            )
        return len(pdf_files), total_chunks

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Run semantic retrieval and return formatted matches."""
        return self.retriever.search(query=query, filters=filters, limit=limit)

    def generate_answer(
        self, query: str, context_chunks: list[dict[str, Any]], model: str | None = None
    ) -> str:
        """Generate a final answer from retrieved context chunks."""
        if model:
            self.answer_generator.model = model
        return self.answer_generator.generate(query=query, context_chunks=context_chunks)

    def query(
        self,
        question: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Run end-to-end question answering and return answer with sources."""
        sources = self.search(question, filters=filters, limit=top_k)
        answer = self.generate_answer(question, sources)
        return {"question": question, "answer": answer, "sources": sources}
