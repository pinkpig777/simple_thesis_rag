from pathlib import Path
from typing import Any

import gradio as gr

from src.pipelines.thesis_rag_pipeline import ThesisRAGPipeline
from src.utils.config import RAGConfig


def _to_int(value: Any, default: int) -> int:
    """Convert UI numeric values to int with a fallback default."""
    if value is None:
        return default
    return int(value)


def _to_optional_int(value: Any) -> int | None:
    """Convert UI numeric values to optional int."""
    if value is None:
        return None
    return int(value)


def _build_pipeline(
    qdrant_path: str,
    qdrant_host: str,
    qdrant_port: Any,
    collection: str,
    embedding_model: str,
    chat_model: str,
) -> ThesisRAGPipeline:
    """Create a pipeline from UI settings."""
    config = RAGConfig(
        qdrant_path=qdrant_path.strip() or None,
        qdrant_host=qdrant_host.strip() or "localhost",
        qdrant_port=_to_int(qdrant_port, 6333),
        collection_name=collection.strip() or "thesis_chunks_v2",
        embedding_model=embedding_model.strip() or "text-embedding-3-small",
        chat_model=chat_model.strip() or "gpt-4o-mini",
    )
    return ThesisRAGPipeline(config=config)


def _format_source_title(metadata: dict[str, Any]) -> str:
    """Build a readable source title with disambiguation for generic names."""
    title = str(metadata.get("title") or "Unknown")
    work_title = str(metadata.get("work_title") or "")
    document_type = str(metadata.get("document_type") or "")

    generic_titles = {"manuscript", "paper", "readme", "slides", "published", "unknown"}
    normalized_title = title.strip().lower()
    if work_title and normalized_title in generic_titles:
        title = f"{work_title} ({document_type})" if document_type else work_title

    return title


def _format_sources_markdown(sources: list[dict[str, Any]]) -> str:
    """Format retrieved sources in a readable markdown block."""
    if not sources:
        return "No sources."

    lines = ["### Retrieved Sources", ""]
    for rank, source in enumerate(sources, start=1):
        metadata = source["metadata"]
        title = _format_source_title(metadata)
        filename = str(metadata.get("filename") or "")
        source_path = str(metadata.get("source_path") or "")
        document_id = str(metadata.get("document_id") or "Unknown")
        short_id = document_id[:8] if len(document_id) >= 8 else document_id
        page_number = metadata.get("page_number", "Unknown")
        score = float(source["score"])

        lines.append(f"**[{rank}] {title}**")
        lines.append(f"- Score: `{score:.3f}` | Page: `{page_number}` | Doc: `{short_id}`")
        if filename:
            lines.append(f"- File: `{filename}`")
        if source_path:
            lines.append(f"- Path: `{source_path}`")
        lines.append("")

    return "\n".join(lines).strip()


def setup_collection_ui(
    qdrant_path: str,
    qdrant_host: str,
    qdrant_port: Any,
    collection: str,
    embedding_model: str,
    chat_model: str,
) -> str:
    """Handle collection setup action from the UI."""
    try:
        pipeline = _build_pipeline(
            qdrant_path,
            qdrant_host,
            qdrant_port,
            collection,
            embedding_model,
            chat_model,
        )
        created = pipeline.setup_collection()
        if created:
            return f"Collection `{pipeline.config.collection_name}` created."
        return f"Collection `{pipeline.config.collection_name}` already exists."
    except Exception as exc:
        return f"Error: {exc}"


def ingest_pdf_ui(
    pdf_path: str,
    chunk_size: Any,
    qdrant_path: str,
    qdrant_host: str,
    qdrant_port: Any,
    collection: str,
    embedding_model: str,
    chat_model: str,
) -> str:
    """Handle single-PDF ingestion action from the UI."""
    try:
        pdf = Path(pdf_path.strip())
        if not pdf.exists():
            return f"Error: PDF not found: {pdf}"

        pipeline = _build_pipeline(
            qdrant_path,
            qdrant_host,
            qdrant_port,
            collection,
            embedding_model,
            chat_model,
        )
        pipeline.setup_collection()
        count = pipeline.ingest_pdf(pdf, chunk_size=_to_int(chunk_size, 500))
        return f"Ingested `{pdf}` with {count} chunks."
    except Exception as exc:
        return f"Error: {exc}"


def ingest_dir_ui(
    directory: str,
    pattern: str,
    qdrant_path: str,
    qdrant_host: str,
    qdrant_port: Any,
    collection: str,
    embedding_model: str,
    chat_model: str,
) -> str:
    """Handle directory ingestion action from the UI."""
    try:
        directory_path = Path(directory.strip())
        if not directory_path.exists():
            return f"Error: Directory not found: {directory_path}"

        pipeline = _build_pipeline(
            qdrant_path,
            qdrant_host,
            qdrant_port,
            collection,
            embedding_model,
            chat_model,
        )
        pipeline.setup_collection()
        file_count, chunk_count = pipeline.ingest_directory(
            directory_path, pattern=pattern.strip() or "*.pdf"
        )
        return f"Ingested {file_count} files and {chunk_count} chunks from `{directory_path}`."
    except Exception as exc:
        return f"Error: {exc}"


def query_ui(
    question: str,
    top_k: Any,
    year_min: Any,
    year_max: Any,
    university: str,
    author: str,
    qdrant_path: str,
    qdrant_host: str,
    qdrant_port: Any,
    collection: str,
    embedding_model: str,
    chat_model: str,
) -> tuple[str, str]:
    """Handle question answering action from the UI."""
    try:
        user_question = question.strip()
        if not user_question:
            return "Please enter a question.", ""

        pipeline = _build_pipeline(
            qdrant_path,
            qdrant_host,
            qdrant_port,
            collection,
            embedding_model,
            chat_model,
        )

        filters: dict[str, Any] = {}
        parsed_year_min = _to_optional_int(year_min)
        parsed_year_max = _to_optional_int(year_max)
        if parsed_year_min is not None:
            filters["year_min"] = parsed_year_min
        if parsed_year_max is not None:
            filters["year_max"] = parsed_year_max
        if university.strip():
            filters["university"] = university.strip()
        if author.strip():
            filters["author"] = author.strip()

        result = pipeline.query(
            question=user_question,
            filters=filters or None,
            top_k=_to_int(top_k, 5),
        )

        sources = _format_sources_markdown(result["sources"])
        return result["answer"], sources
    except Exception as exc:
        return f"Error: {exc}", ""


def build_demo() -> gr.Blocks:
    """Construct and wire the Gradio UI."""
    with gr.Blocks(title="Simple Thesis RAG") as demo:
        gr.Markdown("# Simple Thesis RAG")
        gr.Markdown("Direct UI over the local Python RAG pipeline (no separate API server).")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## Settings")
                qdrant_path = gr.Textbox(
                    label="Qdrant Local Path",
                    value="./storage/vectorstore/qdrant",
                    info="Leave empty to use host/port mode.",
                )
                qdrant_host = gr.Textbox(label="Qdrant Host", value="localhost")
                qdrant_port = gr.Number(label="Qdrant Port", value=6333, precision=0)
                collection = gr.Textbox(label="Collection", value="thesis_chunks_v2")
                embedding_model = gr.Textbox(label="Embedding Model", value="text-embedding-3-small")
                chat_model = gr.Textbox(label="Chat Model", value="gpt-4o-mini")

                setup_button = gr.Button("Setup Collection", variant="primary")
                setup_status = gr.Textbox(label="Setup Status", interactive=False)

            with gr.Column(scale=2):
                with gr.Tab("Ingest"):
                    gr.Markdown("### Ingest One PDF")
                    pdf_path = gr.Textbox(
                        label="PDF Path",
                        value="data/raw/Accounting for Wealth Concentration in the United States/Manuscript.pdf",
                    )
                    chunk_size = gr.Number(label="Chunk Size (words)", value=500, precision=0)
                    ingest_pdf_button = gr.Button("Ingest PDF")
                    ingest_pdf_status = gr.Textbox(label="Single PDF Status", interactive=False)

                    gr.Markdown("### Ingest Directory")
                    ingest_dir_path = gr.Textbox(label="Directory", value="data/raw")
                    ingest_pattern = gr.Textbox(label="Glob Pattern", value="*/*.pdf")
                    ingest_dir_button = gr.Button("Ingest Directory")
                    ingest_dir_status = gr.Textbox(label="Directory Status", interactive=False)

                with gr.Tab("Query"):
                    question = gr.Textbox(label="Question", lines=3)
                    top_k = gr.Number(label="Top K", value=5, precision=0)
                    with gr.Row():
                        year_min = gr.Number(label="Year Min", value=None, precision=0)
                        year_max = gr.Number(label="Year Max", value=None, precision=0)
                    with gr.Row():
                        university = gr.Textbox(label="University")
                        author = gr.Textbox(label="Author")
                    query_button = gr.Button("Ask", variant="primary")
                    answer_output = gr.Markdown(label="Answer")
                    sources_output = gr.Markdown(label="Sources")

        setup_button.click(
            setup_collection_ui,
            inputs=[qdrant_path, qdrant_host, qdrant_port, collection, embedding_model, chat_model],
            outputs=[setup_status],
        )

        ingest_pdf_button.click(
            ingest_pdf_ui,
            inputs=[
                pdf_path,
                chunk_size,
                qdrant_path,
                qdrant_host,
                qdrant_port,
                collection,
                embedding_model,
                chat_model,
            ],
            outputs=[ingest_pdf_status],
        )

        ingest_dir_button.click(
            ingest_dir_ui,
            inputs=[
                ingest_dir_path,
                ingest_pattern,
                qdrant_path,
                qdrant_host,
                qdrant_port,
                collection,
                embedding_model,
                chat_model,
            ],
            outputs=[ingest_dir_status],
        )

        query_button.click(
            query_ui,
            inputs=[
                question,
                top_k,
                year_min,
                year_max,
                university,
                author,
                qdrant_path,
                qdrant_host,
                qdrant_port,
                collection,
                embedding_model,
                chat_model,
            ],
            outputs=[answer_output, sources_output],
        )

    return demo


def main() -> None:
    """Launch the Gradio app."""
    demo = build_demo()
    demo.launch()


if __name__ == "__main__":
    main()
