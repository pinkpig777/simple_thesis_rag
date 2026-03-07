import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from src.utils.config import RAGConfig
from src.utils.pipeline_factory import build_pipeline

if TYPE_CHECKING:
    from src.pipelines.thesis_rag_pipeline import ThesisRAGPipeline


DEFAULT_CONFIG = RAGConfig()


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Simple thesis RAG CLI")
    parser.add_argument(
        "--qdrant-path",
        help="Use embedded local Qdrant storage path instead of host/port",
    )
    parser.add_argument("--qdrant-host", default=DEFAULT_CONFIG.qdrant_host)
    parser.add_argument("--qdrant-port", type=int, default=DEFAULT_CONFIG.qdrant_port)
    parser.add_argument("--collection", default=DEFAULT_CONFIG.collection_name)
    parser.add_argument("--embedding-model", default=DEFAULT_CONFIG.embedding_model)
    parser.add_argument("--chat-model", default=DEFAULT_CONFIG.chat_model)
    parser.add_argument("--visual-model", default=DEFAULT_CONFIG.visual_description_model)
    parser.add_argument("--mineru-output-root", default=DEFAULT_CONFIG.mineru_output_root)
    parser.add_argument("--visual-description-root", default=DEFAULT_CONFIG.visual_description_root)
    parser.add_argument("--phase12-contract-root", default=DEFAULT_CONFIG.phase12_contract_root)

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("setup", help="Create collection and payload indexes if missing")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest one PDF file")
    ingest_parser.add_argument("--pdf", type=Path, required=True)
    ingest_parser.add_argument("--chunk-size", type=int, default=500)
    ingest_parser.add_argument("--year", type=int)
    ingest_parser.add_argument("--university")
    ingest_parser.add_argument("--author")
    ingest_parser.add_argument("--title")
    ingest_parser.add_argument(
        "--describe-visuals",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Generate image/table/equation descriptions during ingestion.",
    )
    ingest_parser.add_argument(
        "--replace-document",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete existing points for this document_id before upsert.",
    )
    ingest_parser.add_argument(
        "--overwrite-visual-descriptions",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Regenerate all visual descriptions even when cache exists.",
    )

    ingest_dir_parser = subparsers.add_parser("ingest-dir", help="Ingest all PDFs in a folder")
    ingest_dir_parser.add_argument("--dir", type=Path, required=True)
    ingest_dir_parser.add_argument("--pattern", default="*.pdf")
    ingest_dir_parser.add_argument(
        "--describe-visuals",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Generate image/table/equation descriptions during ingestion.",
    )
    ingest_dir_parser.add_argument(
        "--replace-document",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete existing points for each document_id before upsert.",
    )
    ingest_dir_parser.add_argument(
        "--overwrite-visual-descriptions",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Regenerate all visual descriptions even when cache exists.",
    )

    query_parser = subparsers.add_parser("query", help="Query and generate an answer")
    query_parser.add_argument("--question", required=True)
    query_parser.add_argument("--top-k", type=int, default=5)
    query_parser.add_argument("--year-min", type=int)
    query_parser.add_argument("--year-max", type=int)
    query_parser.add_argument("--university")
    query_parser.add_argument("--author")

    return parser


def _build_pipeline(args: argparse.Namespace) -> "ThesisRAGPipeline":
    """Create a configured pipeline instance from parsed CLI arguments."""
    return build_pipeline(
        qdrant_path=args.qdrant_path,
        qdrant_host=args.qdrant_host,
        qdrant_port=args.qdrant_port,
        collection_name=args.collection,
        embedding_model=args.embedding_model,
        chat_model=args.chat_model,
        visual_description_model=args.visual_model,
        mineru_output_root=args.mineru_output_root,
        visual_description_root=args.visual_description_root,
        phase12_contract_root=args.phase12_contract_root,
    )


def _metadata_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    """Map optional metadata flags into a metadata dict."""
    metadata: dict[str, Any] = {}
    for key in ("year", "university", "author", "title"):
        value = getattr(args, key, None)
        if value is not None:
            metadata[key] = value
    return metadata or None


def _filters_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    """Map optional query filter flags into a filter dict."""
    filters: dict[str, Any] = {}
    if getattr(args, "year_min", None) is not None:
        filters["year_min"] = args.year_min
    if getattr(args, "year_max", None) is not None:
        filters["year_max"] = args.year_max
    if getattr(args, "university", None):
        filters["university"] = args.university
    if getattr(args, "author", None):
        filters["author"] = args.author
    return filters or None


def _format_source_label(metadata: dict[str, Any]) -> str:
    """Build a readable source label with disambiguating metadata."""
    title = str(metadata.get("title") or "Unknown")
    work_title = str(metadata.get("work_title") or "")
    document_type = str(metadata.get("document_type") or "")
    filename = str(metadata.get("filename") or "")
    source_path = str(metadata.get("source_path") or "")
    document_id = str(metadata.get("document_id") or "Unknown")

    # For generic titles like "Manuscript", prefer a fuller work title when available.
    generic_titles = {"manuscript", "paper", "readme", "slides", "published", "unknown"}
    normalized_title = title.strip().lower()
    if work_title and normalized_title in generic_titles:
        if document_type:
            title = f"{work_title} ({document_type})"
        else:
            title = work_title

    short_id = document_id[:8] if len(document_id) >= 8 else document_id
    extras = [
        f"path: {source_path}" if source_path else "",
        f"file: {filename}" if filename else "",
        f"doc: {short_id}" if short_id else "",
    ]
    extras = [extra for extra in extras if extra]

    if extras:
        return f"{title} | " + " | ".join(extras)
    return title


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process-style exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        rag = _build_pipeline(args)

        if args.command == "setup":
            created = rag.setup_collection()
            message = "Collection created." if created else "Collection already exists."
            print(message)
            return 0

        if args.command == "ingest":
            rag.setup_collection()
            chunk_count = rag.ingest_pdf(
                args.pdf,
                metadata=_metadata_from_args(args),
                chunk_size=args.chunk_size,
                describe_visuals=args.describe_visuals,
                replace_document=args.replace_document,
                overwrite_visual_descriptions=args.overwrite_visual_descriptions,
            )
            print(f"Ingested {args.pdf} ({chunk_count} chunks).")
            return 0

        if args.command == "ingest-dir":
            rag.setup_collection()
            file_count, chunk_count = rag.ingest_directory(
                args.dir,
                pattern=args.pattern,
                describe_visuals=args.describe_visuals,
                replace_document=args.replace_document,
                overwrite_visual_descriptions=args.overwrite_visual_descriptions,
            )
            print(f"Ingested {file_count} files ({chunk_count} chunks) from {args.dir}.")
            return 0

        if args.command == "query":
            result = rag.query(
                args.question,
                filters=_filters_from_args(args),
                top_k=args.top_k,
            )
            print(result["answer"])
            print("\nSources:")
            for source in result["sources"]:
                metadata = source["metadata"]
                print(
                    f"- {_format_source_label(metadata)} (p.{metadata['page_number']}), "
                    f"score: {source['score']:.3f}"
                )
            return 0

    except Exception as exc:
        message = str(exc)
        if "Connection refused" in message:
            if args.qdrant_path:
                print(f"Error: Could not open local Qdrant at path: {args.qdrant_path}")
            else:
                print(
                    "Error: Could not connect to Qdrant at "
                    f"{args.qdrant_host}:{args.qdrant_port}."
                )
                print(
                    "Hint: start Qdrant or use local mode with "
                    "--qdrant-path ./storage/vectorstore/qdrant"
                )
        else:
            print(f"Error: {exc}")
        return 1

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
