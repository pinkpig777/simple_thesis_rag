from typing import Any, Sequence
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
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
        self.is_local = bool(qdrant_path)
        if qdrant_path:
            self.client = QdrantClient(path=qdrant_path)
        else:
            self.client = QdrantClient(host=host, port=port)
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim

    def collection_exists(self) -> bool:
        collections = self.client.get_collections().collections
        return any(collection.name == self.collection_name for collection in collections)

    def setup_collection(self) -> bool:
        if self.collection_exists():
            return False

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.embedding_dim, distance=Distance.COSINE),
        )

        if not self.is_local:
            indexes = [
                ("document_id", "keyword"),
                ("year", "integer"),
                ("university", "keyword"),
                ("author", "text"),
                ("chunk_type", "keyword"),
                ("page_number", "integer"),
            ]
            for field_name, field_type in indexes:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                )

        return True

    def upsert_chunks(
        self,
        chunks: Sequence[dict[str, Any]],
        embedder: Any,
        batch_size: int = 100,
    ) -> int:
        points: list[PointStruct] = []
        for chunk_index, chunk in enumerate(chunks):
            # Qdrant accepts only integer or UUID point IDs.
            point_id = str(uuid5(NAMESPACE_URL, f"{chunk['document_id']}:{chunk_index}"))
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

    def search(
        self,
        query_vector: Sequence[float],
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ):
        return self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=self._build_filter(filters),
            limit=limit,
            with_payload=True,
        )

    @staticmethod
    def _build_filter(filters: dict[str, Any] | None) -> Filter | None:
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
