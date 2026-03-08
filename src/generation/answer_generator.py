import re
from typing import Any, Sequence

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI


class AnswerGenerator:
    SOURCE_TAG_PATTERN = re.compile(r"\[S(\d+)\]")
    SYSTEM_PROMPT = (
        "You are a helpful research assistant that answers questions based on thesis documents. "
        "Write a clear answer with inline evidence tags. "
        "Use only source tags in the form [S1], [S2], etc. from the provided context. "
        "Do not invent source tags. "
        "Preserve mathematical expressions in LaTeX format when they appear in the context or question."
    )

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        client: "OpenAI | None" = None,
    ) -> None:
        """Initialize answer generation settings and optional OpenAI client."""
        self.model = model
        self._client = client

    @property
    def client(self):
        """Lazily initialize and return the OpenAI client."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI()
        return self._client

    @classmethod
    def _extract_source_tag_ids(cls, text: str) -> set[int]:
        """Extract numeric source tag ids from answer text (e.g., [S1], [S2])."""
        source_ids: set[int] = set()
        for match in cls.SOURCE_TAG_PATTERN.finditer(text):
            source_ids.add(int(match.group(1)))
        return source_ids

    def generate(self, query: str, context_chunks: Sequence[dict[str, Any]]) -> str:
        """Generate a cited answer and validate citation tags against provided sources."""
        if not context_chunks:
            return "I could not find relevant sources to answer that question."

        context_blocks: list[str] = []
        for index, chunk in enumerate(context_chunks, start=1):
            metadata = chunk.get("metadata") or {}
            title = str(metadata.get("title") or "Unknown")
            page_number = metadata.get("page_number", "Unknown")
            chunk_type = str(chunk.get("chunk_type") or "text")
            context_blocks.append(
                f"[S{index}] title={title}; page={page_number}; type={chunk_type}\n{chunk['text']}"
            )
        context = "\n\n".join(context_blocks)

        prompt = (
            "Based on the following labeled excerpts from thesis documents, answer the question.\n"
            "Rules:\n"
            "- Cite evidence inline using [S#] tags (for example: [S1], [S3]).\n"
            "- Every factual claim should be supported by at least one [S#] tag.\n"
            "- Use only source tags that appear in the provided context labels.\n"
            "- Do not output a references section; citations should remain inline only.\n"
            "- Preserve LaTeX math notation (keep $...$ and $$...$$).\n\n"
            f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content
        answer = content.strip() if content else ""
        tag_ids = self._extract_source_tag_ids(answer)
        max_source_id = len(context_chunks)
        invalid_tag_ids = sorted(tag_id for tag_id in tag_ids if tag_id < 1 or tag_id > max_source_id)
        if invalid_tag_ids:
            allowed_range = f"[S1]..[S{max_source_id}]"
            raise ValueError(
                "Generated answer contains invalid source tags: "
                f"{', '.join(f'[S{tag_id}]' for tag_id in invalid_tag_ids)}; "
                f"allowed range is {allowed_range}."
            )
        return answer
