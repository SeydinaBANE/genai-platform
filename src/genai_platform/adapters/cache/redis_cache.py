import hashlib
from typing import Any


class SemanticCache:
    def __init__(self, redis_url: str, ttl: int = 3600) -> None:
        self.redis_url = redis_url
        self.ttl = ttl
        self._client: Any = None

    async def _get_client(self) -> Any:
        if self._client is None:
            try:
                import redis.asyncio as aioredis

                self._client = aioredis.from_url(self.redis_url, decode_responses=True)
            except ImportError:
                self._client = None
        return self._client

    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()

    async def get(self, query: str) -> str | None:
        client = await self._get_client()
        if not client:
            return None
        key = self._hash_query(query)
        try:
            value = await client.get(key)
            return value  # type: ignore[no-any-return]
        except Exception:
            return None

    async def set(self, query: str, response: str) -> None:
        client = await self._get_client()
        if not client:
            return
        key = self._hash_query(query)
        try:
            await client.setex(key, self.ttl, response)
        except Exception:
            return

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
