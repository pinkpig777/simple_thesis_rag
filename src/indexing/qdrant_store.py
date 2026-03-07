from typing import Any, Sequence
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)


class QdrantStore:
    def __init__(
        self,
        qdrant_path: str | None = None,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "thesis_chunks",
        embedding_dim: int = 1536,
    ) -> None:
        """Create a Qdrant client in local-path mode or host/port mode."""
        self.is_local = bool(qdrant_path)
        if qdrant_path:
            self.client = QdrantClient(path=qdrant_path)
        else:
            self.client = QdrantClient(host=host, port=port)
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim

    def collection_exists(self) -> bool:
        """Return True when the target collection already exists."""
        collections = self.client.get_collections().collections
        return any(collection.name == self.collection_name for collection in collections)

    def setup_collection(self) -> bool:
        """Create the collection and indexes when missing."""
        created_collection = False
        if not self.collection_exists():
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.embedding_dim, distance=Distance.COSINE),
            )
            created_collection = True

        if not self.is_local:
            self._ensure_payload_indexes()

        return created_collection

    def _ensure_payload_indexes(self) -> None:
        """Ensure payload indexes are present for common metadata filters."""
        indexes = [
            ("document_id", "keyword"),
            ("year", "integer"),
            ("university", "keyword"),
            ("author", "keyword"),
            ("work_title", "text"),
            ("document_type", "keyword"),
            ("chunk_type", "keyword"),
            ("visual_type", "keyword"),
            ("page_number", "integer"),
        ]
        for field_name, field_type in indexes:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field_name,
                field_schema=field_type,
            )

    def upsert_chunks(
        self,
        chunks: Sequence[dict[str, Any]],
        embedder: Any,
        batch_size: int = 100,
    ) -> int:
        """Embed and upsert chunk payloads in batches."""
        points: list[PointStruct] = []
        for chunk_index, chunk in enumerate(chunks):
            # Qdrant accepts only integer or UUID point IDs.
            point_key = str(chunk.get("chunk_id") or f"{chunk['document_id']}:{chunk_index}")
            point_id = str(uuid5(NAMESPACE_URL, point_key))
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedder.embed(chunk["text"]),
                    payload=chunk,
                )
            )
            if len(points) >= batch_size:
                self.client.upsert(collection_name=self.collection_name, points=points)
                points = []

        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

        return len(chunks)

    def delete_document(self, document_id: str) -> None:
        """Delete all points associated with one document id."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def search(
        self,
        query_vector: Sequence[float],
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ):
        """Run a vector similarity query with optional metadata filters."""
        query_filter = self._build_filter(filters)

        # qdrant-client >= 1.16 uses query_points; older versions use search.
        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            return response.points

        return self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

    @staticmethod
    def _build_filter(filters: dict[str, Any] | None) -> Filter | None:
        """Translate app-level filter dicts into a Qdrant filter object."""
        if not filters:
            return None

        conditions: list[FieldCondition] = []
        if "year_min" in filters:
            conditions.append(
                FieldCondition(
                    key="year",
                    range=Range(
                        gte=filters["year_min"],
                        lte=filters.get("year_max", 2030),
                    ),
                )
            )
        if "university" in filters:
            conditions.append(
                FieldCondition(
                    key="university",
                    match=MatchValue(value=filters["university"]),
                )
            )
        if "author" in filters:
            conditions.append(
                FieldCondition(
                    key="author",
                    match=MatchValue(value=filters["author"]),
                )
            )

        if not conditions:
            return None
        return Filter(must=conditions)
