from unittest.mock import patch

import pytest

from genai_platform.cache import SemanticCache


@pytest.mark.asyncio
async def test_cache_redis_unavailable_returns_none() -> None:
    cache = SemanticCache(redis_url="redis://nonexistent:6379/0")
    result = await cache.get("test query")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_redis_unavailable_no_error() -> None:
    cache = SemanticCache(redis_url="redis://nonexistent:6379/0")
    await cache.set("test query", "response")
    result = await cache.get("test query")
    assert result is None


def test_hash_query_consistent() -> None:
    cache = SemanticCache(redis_url="redis://localhost:6379/0")
    h1 = cache._hash_query("hello world")
    h2 = cache._hash_query("hello world")
    assert h1 == h2
    assert len(h1) == 64


def test_hash_query_different_for_different_inputs() -> None:
    cache = SemanticCache(redis_url="redis://localhost:6379/0")
    h1 = cache._hash_query("hello world")
    h2 = cache._hash_query("hello World")
    assert h1 != h2


@pytest.mark.asyncio
async def test_cache_close_without_client() -> None:
    cache = SemanticCache(redis_url="redis://localhost:6379/0")
    await cache.close()


@pytest.mark.asyncio
async def test_cache_get_handles_client_error() -> None:
    cache = SemanticCache(redis_url="redis://localhost:6379/0")
    with patch.object(cache, "_get_client", return_value=None):
        result = await cache.get("test")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_handles_client_error() -> None:
    cache = SemanticCache(redis_url="redis://localhost:6379/0")
    with patch.object(cache, "_get_client", return_value=None):
        await cache.set("test", "response")
