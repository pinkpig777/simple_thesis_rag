import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from src.utils.config import RAGConfig

if TYPE_CHECKING:
    from src.pipelines.thesis_rag_pipeline import ThesisRAGPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simple thesis RAG CLI")
    parser.add_argument("--qdrant-host", default="localhost")
    parser.add_argument("--qdrant-port", type=int, default=6333)
    parser.add_argument("--collection", default="thesis_chunks")
    parser.add_argument("--embedding-model", default="text-embedding-3-small")
    parser.add_argument("--chat-model", default="gpt-4o-mini")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("setup", help="Create collection and payload indexes if missing")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest one PDF file")
    ingest_parser.add_argument("--pdf", type=Path, required=True)
    ingest_parser.add_argument("--chunk-size", type=int, default=500)
    ingest_parser.add_argument("--year", type=int)
    ingest_parser.add_argument("--university")
    ingest_parser.add_argument("--author")
    ingest_parser.add_argument("--title")

    ingest_dir_parser = subparsers.add_parser("ingest-dir", help="Ingest all PDFs in a folder")
    ingest_dir_parser.add_argument("--dir", type=Path, required=True)
    ingest_dir_parser.add_argument("--pattern", default="*.pdf")

    query_parser = subparsers.add_parser("query", help="Query and generate an answer")
    query_parser.add_argument("--question", required=True)
    query_parser.add_argument("--top-k", type=int, default=5)
    query_parser.add_argument("--year-min", type=int)
    query_parser.add_argument("--year-max", type=int)
    query_parser.add_argument("--university")
    query_parser.add_argument("--author")

    return parser


def _build_pipeline(args: argparse.Namespace) -> "ThesisRAGPipeline":
    from src.pipelines.thesis_rag_pipeline import ThesisRAGPipeline

    config = RAGConfig(
        qdrant_host=args.qdrant_host,
        qdrant_port=args.qdrant_port,
        collection_name=args.collection,
        embedding_model=args.embedding_model,
        chat_model=args.chat_model,
    )
    return ThesisRAGPipeline(config=config)


def _metadata_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    metadata: dict[str, Any] = {}
    for key in ("year", "university", "author", "title"):
        value = getattr(args, key, None)
        if value is not None:
            metadata[key] = value
    return metadata or None


def _filters_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
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


def main(argv: Sequence[str] | None = None) -> int:
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
            )
            print(f"Ingested {args.pdf} ({chunk_count} chunks).")
            return 0

        if args.command == "ingest-dir":
            rag.setup_collection()
            file_count, chunk_count = rag.ingest_directory(args.dir, pattern=args.pattern)
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
                    f"- {metadata['title']} (p.{metadata['page_number']}), "
                    f"score: {source['score']:.3f}"
                )
            return 0

    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
