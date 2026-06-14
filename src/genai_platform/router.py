from fastapi import APIRouter

from genai_platform.schemas import QueryRequest, QueryResponse

v1_router = APIRouter()


@v1_router.post("/query")
async def query(request: QueryRequest) -> QueryResponse:  # noqa: ARG001
    return QueryResponse(
        content="Query received",
        model="placeholder",
        from_cache=False,
        latency_ms=0,
        tokens_used=0,
    )


@v1_router.get("/models")
async def list_models() -> list[str]:
    return ["gpt-4o", "claude-3-sonnet", "mistral-large"]
