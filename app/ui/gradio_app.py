from pathlib import Path
from typing import Any

import gradio as gr

from src.pipelines.thesis_rag_pipeline import ThesisRAGPipeline
from src.utils.config import RAGConfig
from src.utils.pipeline_factory import build_pipeline
from src.utils.source_formatting import build_visual_preview_cards, format_sources_markdown


DEFAULT_CONFIG = RAGConfig()


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


def _resolve_pdf_path(uploaded_pdf: Any, pdf_path: str) -> Path:
    """Resolve PDF input from upload widget first, then fallback textbox path."""
    if isinstance(uploaded_pdf, str) and uploaded_pdf.strip():
        return Path(uploaded_pdf.strip())
    return Path(pdf_path.strip())


def _build_pipeline(
    qdrant_path: str,
    qdrant_host: str,
    qdrant_port: Any,
    collection: str,
    embedding_model: str,
    chat_model: str,
    visual_model: str,
    mineru_output_root: str,
    visual_description_root: str,
    phase12_contract_root: str,
) -> ThesisRAGPipeline:
    """Create a pipeline from UI settings."""
    return build_pipeline(
        qdrant_path=qdrant_path,
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        collection_name=collection,
        embedding_model=embedding_model,
        chat_model=chat_model,
        visual_description_model=visual_model,
        mineru_output_root=mineru_output_root,
        visual_description_root=visual_description_root,
        phase12_contract_root=phase12_contract_root,
    )


def setup_collection_ui(
    qdrant_path: str,
    qdrant_host: str,
    qdrant_port: Any,
    collection: str,
    embedding_model: str,
    chat_model: str,
    visual_model: str,
    mineru_output_root: str,
    visual_description_root: str,
    phase12_contract_root: str,
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
            visual_model,
            mineru_output_root,
            visual_description_root,
            phase12_contract_root,
        )
        created = pipeline.setup_collection()
        if created:
            return f"Collection `{pipeline.config.collection_name}` created."
        return f"Collection `{pipeline.config.collection_name}` already exists."
    except Exception as exc:
        return f"Error: {exc}"


def ingest_pdf_ui(
    uploaded_pdf: Any,
    pdf_path: str,
    chunk_size: Any,
    describe_visuals: bool,
    replace_document: bool,
    overwrite_visual_descriptions: bool,
    qdrant_path: str,
    qdrant_host: str,
    qdrant_port: Any,
    collection: str,
    embedding_model: str,
    chat_model: str,
    visual_model: str,
    mineru_output_root: str,
    visual_description_root: str,
    phase12_contract_root: str,
) -> str:
    """Handle single-PDF ingestion action from the UI."""
    try:
        pdf = _resolve_pdf_path(uploaded_pdf, pdf_path)
        if not pdf.exists():
            return f"Error: PDF not found: {pdf}"

        pipeline = _build_pipeline(
            qdrant_path,
            qdrant_host,
            qdrant_port,
            collection,
            embedding_model,
            chat_model,
            visual_model,
            mineru_output_root,
            visual_description_root,
            phase12_contract_root,
        )
        pipeline.setup_collection()
        count = pipeline.ingest_pdf(
            pdf,
            chunk_size=_to_int(chunk_size, 500),
            describe_visuals=describe_visuals,
            replace_document=replace_document,
            overwrite_visual_descriptions=overwrite_visual_descriptions,
        )
        return f"Ingested `{pdf}` with {count} chunks."
    except Exception as exc:
        return f"Error: {exc}"


def ingest_dir_ui(
    directory: str,
    pattern: str,
    describe_visuals: bool,
    replace_document: bool,
    overwrite_visual_descriptions: bool,
    qdrant_path: str,
    qdrant_host: str,
    qdrant_port: Any,
    collection: str,
    embedding_model: str,
    chat_model: str,
    visual_model: str,
    mineru_output_root: str,
    visual_description_root: str,
    phase12_contract_root: str,
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
            visual_model,
            mineru_output_root,
            visual_description_root,
            phase12_contract_root,
        )
        pipeline.setup_collection()
        file_count, chunk_count = pipeline.ingest_directory(
            directory_path,
            pattern=pattern.strip() or "*.pdf",
            describe_visuals=describe_visuals,
            replace_document=replace_document,
            overwrite_visual_descriptions=overwrite_visual_descriptions,
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
    visual_model: str,
    mineru_output_root: str,
    visual_description_root: str,
    phase12_contract_root: str,
) -> tuple[str, str, list[tuple[str, str]]]:
    """Handle question answering action from the UI."""
    try:
        user_question = question.strip()
        if not user_question:
            return "Please enter a question.", "", []

        pipeline = _build_pipeline(
            qdrant_path,
            qdrant_host,
            qdrant_port,
            collection,
            embedding_model,
            chat_model,
            visual_model,
            mineru_output_root,
            visual_description_root,
            phase12_contract_root,
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

        sources = format_sources_markdown(result["sources"])
        visual_cards = build_visual_preview_cards(result["sources"])
        return result["answer"], sources, visual_cards
    except Exception as exc:
        return f"Error: {exc}", "", []


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
                qdrant_host = gr.Textbox(label="Qdrant Host", value=DEFAULT_CONFIG.qdrant_host)
                qdrant_port = gr.Number(label="Qdrant Port", value=DEFAULT_CONFIG.qdrant_port, precision=0)
                collection = gr.Textbox(label="Collection", value=DEFAULT_CONFIG.collection_name)
                embedding_model = gr.Textbox(label="Embedding Model", value=DEFAULT_CONFIG.embedding_model)
                chat_model = gr.Textbox(label="Chat Model", value=DEFAULT_CONFIG.chat_model)
                visual_model = gr.Textbox(
                    label="Visual Description Model", value=DEFAULT_CONFIG.visual_description_model
                )
                mineru_output_root = gr.Textbox(
                    label="MinerU Output Root",
                    value=DEFAULT_CONFIG.mineru_output_root,
                )
                visual_description_root = gr.Textbox(
                    label="Visual Description Cache Root",
                    value=DEFAULT_CONFIG.visual_description_root,
                )
                phase12_contract_root = gr.Textbox(
                    label="Phase1->Phase2 Contract Root",
                    value=DEFAULT_CONFIG.phase12_contract_root,
                )

                setup_button = gr.Button("Setup Collection", variant="primary")
                setup_status = gr.Textbox(label="Setup Status", interactive=False)

            with gr.Column(scale=2):
                with gr.Tab("Ingest"):
                    gr.Markdown("### Ingest One PDF")
                    uploaded_pdf = gr.File(
                        label="Upload PDF",
                        file_types=[".pdf"],
                        type="filepath",
                    )
                    pdf_path = gr.Textbox(
                        label="PDF Path (fallback)",
                        value="",
                    )
                    chunk_size = gr.Number(label="Chunk Size (words)", value=500, precision=0)
                    with gr.Row():
                        describe_visuals = gr.Checkbox(
                            label="Describe visuals (image/table/equation)",
                            value=True,
                        )
                        replace_document = gr.Checkbox(
                            label="Replace existing document in collection",
                            value=True,
                        )
                        overwrite_visual_descriptions = gr.Checkbox(
                            label="Overwrite visual cache",
                            value=False,
                        )
                    ingest_pdf_button = gr.Button("Ingest PDF")
                    ingest_pdf_status = gr.Textbox(label="Single PDF Status", interactive=False)

                    gr.Markdown("### Ingest Directory")
                    ingest_dir_path = gr.Textbox(label="Directory", value="data/raw")
                    ingest_pattern = gr.Textbox(label="Glob Pattern", value="*/*.pdf")
                    with gr.Row():
                        dir_describe_visuals = gr.Checkbox(
                            label="Describe visuals (directory)",
                            value=True,
                        )
                        dir_replace_document = gr.Checkbox(
                            label="Replace existing documents",
                            value=True,
                        )
                        dir_overwrite_visual_descriptions = gr.Checkbox(
                            label="Overwrite visual cache",
                            value=False,
                        )
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
                    cited_images_output = gr.Gallery(
                        label="Visual Preview Cards (Cited Evidence)",
                        columns=4,
                        height="auto",
                    )

        setup_button.click(
            setup_collection_ui,
            inputs=[
                qdrant_path,
                qdrant_host,
                qdrant_port,
                collection,
                embedding_model,
                chat_model,
                visual_model,
                mineru_output_root,
                visual_description_root,
                phase12_contract_root,
            ],
            outputs=[setup_status],
        )

        ingest_pdf_button.click(
            ingest_pdf_ui,
            inputs=[
                uploaded_pdf,
                pdf_path,
                chunk_size,
                describe_visuals,
                replace_document,
                overwrite_visual_descriptions,
                qdrant_path,
                qdrant_host,
                qdrant_port,
                collection,
                embedding_model,
                chat_model,
                visual_model,
                mineru_output_root,
                visual_description_root,
                phase12_contract_root,
            ],
            outputs=[ingest_pdf_status],
        )

        ingest_dir_button.click(
            ingest_dir_ui,
            inputs=[
                ingest_dir_path,
                ingest_pattern,
                dir_describe_visuals,
                dir_replace_document,
                dir_overwrite_visual_descriptions,
                qdrant_path,
                qdrant_host,
                qdrant_port,
                collection,
                embedding_model,
                chat_model,
                visual_model,
                mineru_output_root,
                visual_description_root,
                phase12_contract_root,
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
                visual_model,
                mineru_output_root,
                visual_description_root,
                phase12_contract_root,
            ],
            outputs=[answer_output, sources_output, cited_images_output],
        )

    return demo


def main() -> None:
    """Launch the Gradio app."""
    demo = build_demo()
    demo.launch()


if __name__ == "__main__":
    main()
