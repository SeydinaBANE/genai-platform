import pytest
from httpx import ASGITransport, AsyncClient

from genai_platform.api import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_returns_healthy(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_ready_returns_ready(client: AsyncClient):
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_query_endpoint_accepts_valid_request(client: AsyncClient):
    response = await client.post(
        "/api/v1/query",
        json={"query": "What is RAG?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "model" in data
    assert "from_cache" in data


@pytest.mark.asyncio
async def test_query_rejects_empty_query(client: AsyncClient):
    response = await client.post(
        "/api/v1/query",
        json={"query": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_query_rejects_too_long_query(client: AsyncClient):
    response = await client.post(
        "/api/v1/query",
        json={"query": "x" * 10001},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_models_returns_model_list(client: AsyncClient):
    response = await client.get("/api/v1/models")
    assert response.status_code == 200
    models = response.json()
    assert isinstance(models, list)
    assert len(models) > 0
