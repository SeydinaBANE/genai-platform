from typing import Protocol

from genai_platform.domain.models import Chunk, ScoredChunk


class VectorStorePort(Protocol):
    @property
    def ready(self) -> bool: ...

    async def ensure_collection(self, collection: str, vector_size: int) -> None: ...

    async def upsert(
        self,
        collection: str,
        doc_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
        source: str,
    ) -> None: ...

    async def search(
        self, collection: str, query_vector: list[float], limit: int
    ) -> list[ScoredChunk]: ...

    async def close(self) -> None: ...
