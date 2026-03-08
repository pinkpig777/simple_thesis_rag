from typing import Any, Sequence

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI


class AnswerGenerator:
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

    def generate(self, query: str, context_chunks: Sequence[dict[str, Any]]) -> str:
        """Generate a clean answer from retrieved context chunks."""
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
        return content.strip() if content else ""
