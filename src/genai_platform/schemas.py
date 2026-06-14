from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    use_cache: bool = True
    max_contexts: int = Field(default=5, ge=1, le=50)
    model: str | None = None


class QueryResponse(BaseModel):
    content: str
    model: str
    from_cache: bool
    latency_ms: int
    tokens_used: int
    contexts: list[str] | None = None
    guardrail_triggered: bool = False
