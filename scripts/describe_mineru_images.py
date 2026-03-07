#!/usr/bin/env python3
"""Generate OpenAI descriptions for MinerU extracted visual assets."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.ingestion.visual_describer import DEFAULT_VISUAL_TYPES, describe_visual_assets


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for MinerU visual description generation."""
    parser = argparse.ArgumentParser(
        description=(
            "Describe MinerU extracted visual assets and write a JSON index that "
            "links each description back to its source image."
        )
    )
    parser.add_argument(
        "--input-path",
        type=Path,
        required=True,
        help=(
            "Path to a MinerU output directory or a specific *_content_list.json "
            "file. Directory mode scans recursively."
        ),
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Output JSON path. Defaults to <input-path>/image_descriptions.json.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model used for image description.",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=list(DEFAULT_VISUAL_TYPES),
        help="MinerU item types to process (default: image table equation).",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        help="Optional limit on number of assets to process.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Ignore existing output and regenerate all descriptions.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan MinerU outputs and print counts without calling OpenAI.",
    )
    parser.add_argument(
        "--api-key",
        help="Optional API key override. Defaults to OPENAI_API_KEY env var.",
    )
    return parser.parse_args()


def main() -> int:
    """Run CLI flow for MinerU visual description generation."""
    args = parse_args()
    allowed_types = {item_type.strip().lower() for item_type in args.types if item_type.strip()}

    payload = describe_visual_assets(
        input_path=args.input_path,
        output_path=args.output_file,
        model=args.model,
        allowed_types=allowed_types,
        max_items=args.max_items,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        api_key=args.api_key,
        progress=print,
    )

    if args.dry_run:
        print(f"Found {payload['discovered_items']} matching visual assets.")
        print("Dry run: no OpenAI calls made.")
        return 0

    print(f"Saved {payload['total_items']} records to {payload['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
