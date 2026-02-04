from typing import Any


class Retriever:
    def __init__(self, store: Any, embedder: Any) -> None:
        """Initialize retriever dependencies."""
        self.store = store
        self.embedder = embedder

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return formatted top-k retrieval results for a user query."""
        query_embedding = self.embedder.embed(query)
        results = self.store.search(query_embedding, filters=filters, limit=limit)

        formatted_results: list[dict[str, Any]] = []
        for result in results:
            payload = result.payload or {}
            formatted_results.append(
                {
                    "score": float(result.score),
                    "text": payload.get("text", ""),
                    "metadata": {
                        "document_id": payload.get("document_id", "Unknown"),
                        "title": payload.get("title", "Unknown"),
                        "work_title": payload.get("work_title", ""),
                        "document_type": payload.get("document_type", ""),
                        "filename": payload.get("filename", ""),
                        "source_path": payload.get("source_path", ""),
                        "author": payload.get("author", "Unknown"),
                        "year": payload.get("year", "Unknown"),
                        "page_number": payload.get("page_number", "Unknown"),
                    },
                }
            )

        return formatted_results
