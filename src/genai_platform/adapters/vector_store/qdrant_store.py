import uuid
from typing import Any

from genai_platform.domain.models import Chunk, ScoredChunk


class QdrantVectorStore:
    def __init__(self, url: str) -> None:
        from qdrant_client import AsyncQdrantClient

        self._client: Any = AsyncQdrantClient(url=url)
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    async def ensure_collection(self, collection: str, vector_size: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        try:
            collections = await self._client.get_collections()
            exists = any(c.name == collection for c in collections.collections)
            if not exists:
                await self._client.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
            self._ready = True
        except Exception:
            self._ready = False

    async def upsert(
        self,
        collection: str,
        doc_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
        source: str,
    ) -> None:
        from qdrant_client.models import PointStruct

        if not self._ready:
            return

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=v,
                payload={
                    "text": c.text,
                    "doc_id": doc_id,
                    "source": source,
                    "chunk_index": i,
                },
            )
            for i, (c, v) in enumerate(zip(chunks, vectors, strict=True))
        ]
        await self._client.upsert(collection_name=collection, points=points)

    async def search(
        self, collection: str, query_vector: list[float], limit: int
    ) -> list[ScoredChunk]:
        if not self._ready:
            return []

        results = await self._client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
        )
        return [
            ScoredChunk(
                chunk=Chunk(
                    text=r.payload.get("text", ""),
                    metadata={"source": r.payload.get("source", "unknown")},
                ),
                score=r.score,
                source="vector",
            )
            for r in results
        ]

    async def close(self) -> None:
        if self._client:
            await self._client.close()
        self._ready = False
