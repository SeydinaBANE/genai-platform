import pytest
from pydantic import ValidationError

from genai_platform.adapters.http.schemas import QueryRequest, QueryResponse


class TestQueryRequest:
    def test_valid_request(self):
        req = QueryRequest(query="What is RAG?")
        assert req.query == "What is RAG?"
        assert req.use_cache is True
        assert req.max_contexts == 5
        assert req.model is None

    def test_empty_query_raises(self):
        with pytest.raises(ValidationError):
            QueryRequest(query="")

    def test_query_too_long_raises(self):
        with pytest.raises(ValidationError):
            QueryRequest(query="x" * 10001)

    def test_custom_cache_and_contexts(self):
        req = QueryRequest(
            query="Hello",
            use_cache=False,
            max_contexts=10,
            model="gpt-4o",
        )
        assert req.use_cache is False
        assert req.max_contexts == 10
        assert req.model == "gpt-4o"


class TestQueryResponse:
    def test_valid_response(self):
        resp = QueryResponse(
            content="Answer",
            model="gpt-4o",
            from_cache=False,
            latency_ms=1500,
            tokens_used=500,
        )
        assert resp.content == "Answer"
        assert resp.model == "gpt-4o"
        assert resp.latency_ms == 1500

    def test_response_with_optional_fields(self):
        resp = QueryResponse(
            content="Answer",
            model="gpt-4o",
            from_cache=True,
            latency_ms=50,
            tokens_used=0,
            contexts=["doc1", "doc2"],
            guardrail_triggered=True,
        )
        assert resp.contexts == ["doc1", "doc2"]
        assert resp.guardrail_triggered is True
