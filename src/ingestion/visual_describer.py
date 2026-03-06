"""Utilities for describing MinerU visual assets with OpenAI vision models."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Sequence

if TYPE_CHECKING:
    from openai import OpenAI


DEFAULT_VISUAL_TYPES = ("image", "table", "equation")


def discover_content_lists(input_path: Path) -> list[Path]:
    """Resolve one or more MinerU *_content_list.json files from an input path."""
    if input_path.is_file():
        if input_path.name.endswith("_content_list.json"):
            return [input_path.resolve()]
        raise ValueError("Input file must end with '_content_list.json'.")

    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")
    if not input_path.is_dir():
        raise ValueError(f"Input path must be a directory or file: {input_path}")

    matches = sorted(path.resolve() for path in input_path.rglob("*_content_list.json"))
    if not matches:
        raise FileNotFoundError(f"No *_content_list.json files found under: {input_path}")
    return matches


def _coerce_text(value: Any) -> str:
    """Normalize mixed MinerU JSON fields into a single text string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_coerce_text(item) for item in value]
        return " ".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        parts = [_coerce_text(item) for item in value.values()]
        return " ".join(part for part in parts if part).strip()
    return str(value).strip()


def _clip(text: str, max_chars: int = 1200) -> str:
    """Clip long context snippets so prompts stay bounded."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _record_id(content_list_path: Path, item_index: int, image_rel_path: str) -> str:
    """Build a stable record id for one visual item description."""
    raw = f"{content_list_path.resolve()}::{item_index}::{image_rel_path}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def extract_visual_items(content_list_path: Path, allowed_types: set[str]) -> list[dict[str, Any]]:
    """Extract visual item candidates from one MinerU content list."""
    content_list = json.loads(content_list_path.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = []
    source_doc = content_list_path.name.removesuffix("_content_list.json")

    for item_index, item in enumerate(content_list):
        item_type = str(item.get("type") or "").strip().lower()
        if item_type not in allowed_types:
            continue

        image_rel_path = item.get("img_path")
        if not isinstance(image_rel_path, str) or not image_rel_path.strip():
            continue

        image_path = (content_list_path.parent / image_rel_path).resolve()
        if not image_path.exists():
            continue

        page_idx = item.get("page_idx")
        page_number = page_idx + 1 if isinstance(page_idx, int) else None

        context: dict[str, Any] = {}
        if item_type == "image":
            caption = _coerce_text(item.get("image_caption") or item.get("img_caption"))
            footnote = _coerce_text(item.get("image_footnote") or item.get("img_footnote"))
            if caption:
                context["caption"] = _clip(caption)
            if footnote:
                context["footnote"] = _clip(footnote)
        elif item_type == "table":
            caption = _coerce_text(item.get("table_caption"))
            footnote = _coerce_text(item.get("table_footnote"))
            table_body = _coerce_text(item.get("table_body"))
            if caption:
                context["caption"] = _clip(caption)
            if footnote:
                context["footnote"] = _clip(footnote)
            if table_body:
                context["table_body_excerpt"] = _clip(table_body)
        elif item_type == "equation":
            equation_text = _coerce_text(item.get("text"))
            if equation_text:
                context["equation_latex"] = _clip(equation_text)

        items.append(
            {
                "id": _record_id(content_list_path, item_index, image_rel_path),
                "doc_id": source_doc,
                "content_list_path": str(content_list_path.resolve()),
                "item_index": item_index,
                "item_type": item_type,
                "page_idx": page_idx if isinstance(page_idx, int) else None,
                "page_number": page_number,
                "image_rel_path": image_rel_path,
                "image_path": str(image_path),
                "context": context,
            }
        )
    return items


def encode_image_as_data_url(image_path: Path) -> str:
    """Load an image and convert it to a data URL for OpenAI vision input."""
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{image_b64}"


def _extract_message_text(content: Any) -> str:
    """Extract plain text from OpenAI message content payload variants."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
                continue
            text = getattr(part, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return str(content).strip()


def describe_visual_item(client: "OpenAI", model: str, item: dict[str, Any]) -> str:
    """Call OpenAI vision model and return a concise structured description."""
    context_json = json.dumps(item.get("context", {}), ensure_ascii=False, indent=2)
    prompt = (
        "You are helping build a research RAG index.\n"
        f"Describe this extracted {item['item_type']} clearly and factually.\n"
        "Output exactly three sections with these headings:\n"
        "1) Summary\n2) Key details\n3) Potential retrieval keywords\n"
        "Rules:\n"
        "- Do not hallucinate values not visible in the image.\n"
        "- If text is unclear, say it is unclear.\n"
        "- Keep total length under 180 words.\n"
        "- Use plain text only.\n\n"
        f"Structured context from MinerU:\n{context_json}"
    )

    image_path = Path(item["image_path"])
    data_url = encode_image_as_data_url(image_path)

    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate concise, factual descriptions of academic figures, "
                    "tables, and equations."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                ],
            },
        ],
    )
    return _extract_message_text(completion.choices[0].message.content)


def infer_output_path(input_path: Path, output_file: Path | None) -> Path:
    """Resolve final output JSON path from caller inputs."""
    if output_file:
        return output_file.resolve()
    if input_path.is_file():
        return input_path.parent.resolve() / "image_descriptions.json"
    return input_path.resolve() / "image_descriptions.json"


def load_existing_records(output_path: Path) -> dict[str, dict[str, Any]]:
    """Load existing description records keyed by stable id."""
    if not output_path.exists():
        return {}
    data = json.loads(output_path.read_text(encoding="utf-8"))
    records = data.get("items", [])
    return {str(record.get("id")): record for record in records if isinstance(record, dict)}


def build_output_payload(
    *,
    input_path: Path,
    output_path: Path,
    model: str,
    records: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Build final JSON payload for visual description records."""
    sorted_records = sorted(records, key=lambda item: (item["content_list_path"], item["item_index"]))
    index_by_image_path = {record["image_path"]: record["id"] for record in sorted_records}
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path.resolve()),
        "output_path": str(output_path.resolve()),
        "model": model,
        "total_items": len(sorted_records),
        "items": sorted_records,
        "index_by_image_path": index_by_image_path,
    }


def describe_visual_assets(
    *,
    input_path: Path,
    output_path: Path | None = None,
    model: str = "gpt-4o-mini",
    allowed_types: set[str] | None = None,
    max_items: int | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
    api_key: str | None = None,
    client: "OpenAI | None" = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """
    Describe MinerU visual assets and write/update an index JSON payload.

    Returns the final payload object, regardless of whether descriptions were newly
    generated or loaded from cache.
    """
    normalized_input = input_path.resolve()
    normalized_output = infer_output_path(normalized_input, output_path)
    types = {item_type.lower().strip() for item_type in (allowed_types or DEFAULT_VISUAL_TYPES)}
    types = {item_type for item_type in types if item_type}
    if not types:
        raise ValueError("At least one visual type must be provided.")

    content_lists = discover_content_lists(normalized_input)
    visual_items: list[dict[str, Any]] = []
    for content_list_path in content_lists:
        visual_items.extend(extract_visual_items(content_list_path, allowed_types=types))

    if max_items is not None and max_items >= 0:
        visual_items = visual_items[:max_items]

    existing_by_id: dict[str, dict[str, Any]] = {}
    if not overwrite:
        existing_by_id = load_existing_records(normalized_output)

    if progress:
        progress(
            f"discovered={len(visual_items)} content_lists={len(content_lists)} "
            f"output={normalized_output}"
        )

    if not dry_run and visual_items:
        resolved_client: "OpenAI"
        if client is not None:
            resolved_client = client
        else:
            from openai import OpenAI

            resolved_client = OpenAI(api_key=api_key) if api_key else OpenAI()

        for index, item in enumerate(visual_items, start=1):
            record_id = item["id"]
            if record_id in existing_by_id and not overwrite:
                if progress:
                    progress(f"[{index}/{len(visual_items)}] skip {record_id[:8]}")
                continue

            description = describe_visual_item(client=resolved_client, model=model, item=item)
            item["description"] = description
            item["description_model"] = model
            item["described_at"] = datetime.now(timezone.utc).isoformat()
            existing_by_id[record_id] = item
            if progress:
                progress(f"[{index}/{len(visual_items)}] described {record_id[:8]}")

    payload = build_output_payload(
        input_path=normalized_input,
        output_path=normalized_output,
        model=model,
        records=list(existing_by_id.values()),
    )
    payload["discovered_items"] = len(visual_items)

    if dry_run:
        return payload

    normalized_output.parent.mkdir(parents=True, exist_ok=True)
    normalized_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
