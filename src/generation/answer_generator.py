from typing import Any, Sequence

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI


class AnswerGenerator:
    SYSTEM_PROMPT = (
        "You are a helpful research assistant that answers questions based on thesis documents. "
        "Write a clean answer without inline citations, source labels, or page references. "
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

        context = "\n\n".join(
            [
                f"Excerpt {index}:\n{chunk['text']}"
                for index, chunk in enumerate(context_chunks, start=1)
            ]
        )

        prompt = (
            "Based on the following excerpts from thesis documents, answer the "
            "question. Do not include citation markers like '(Manuscript, p.5)', "
            "source names, or page numbers in the answer. Preserve LaTeX math "
            "notation (e.g., keep $...$ and $$...$$) instead of rewriting equations "
            "as plain text.\n\n"
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
