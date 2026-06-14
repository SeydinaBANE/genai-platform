import sys
from unittest.mock import MagicMock

import pytest

from genai_platform.config import Settings
from genai_platform.monitoring import MetricsCollector, PrometheusMetrics


def _make_counter() -> MagicMock:
    def labels(**_: object) -> MagicMock:
        m = MagicMock()
        m.inc = MagicMock()
        return m

    m = MagicMock()
    m.labels = labels
    return m


def _make_histogram() -> MagicMock:
    def labels(**_: object) -> MagicMock:
        m = MagicMock()
        m.observe = MagicMock()
        return m

    m = MagicMock()
    m.labels = labels
    return m


@pytest.fixture(autouse=True)
def _mock_prometheus() -> None:
    prometheus_client = MagicMock()
    prometheus_client.Counter = MagicMock(return_value=_make_counter())
    prometheus_client.Histogram = MagicMock(return_value=_make_histogram())
    sys.modules["prometheus_client"] = prometheus_client
    yield
    sys.modules.pop("prometheus_client", None)


class TestMetricsCollector:
    def test_init_without_langfuse_key(self) -> None:
        settings = Settings(langfuse_public_key="")
        mc = MetricsCollector(settings)
        assert mc._langfuse is None

    def test_init_with_langfuse_key_but_unavailable(self) -> None:
        settings = Settings(
            langfuse_public_key="pk-test",
            langfuse_secret_key="sk-test",  # pragma: allowlist secret
            langfuse_host="http://localhost:3000",
        )
        mc = MetricsCollector(settings)
        langfuse = mc.langfuse
        assert langfuse is None

    def test_trace_query_returns_none_when_no_langfuse(self) -> None:
        settings = Settings(langfuse_public_key="")
        mc = MetricsCollector(settings)
        trace_id = mc.trace_query(
            query="test",
            response="response",
            model="gpt-4o",
            latency_ms=100,
            tokens_prompt=10,
            tokens_completion=20,
        )
        assert trace_id is None

    def test_score_feedback_noop_when_no_langfuse(self) -> None:
        settings = Settings(langfuse_public_key="")
        mc = MetricsCollector(settings)
        mc.score_feedback(trace_id="trace-123", rating=4.5)


class TestPrometheusMetrics:
    def test_init_creates_metrics(self) -> None:
        pm = PrometheusMetrics()
        pm.init()
        assert pm._initialized is True
        assert "requests_total" in pm._metrics

    def test_init_is_idempotent(self) -> None:
        pm = PrometheusMetrics()
        pm.init()
        pm.init()
        assert pm._initialized is True

    def test_record_request_works_after_init(self) -> None:
        pm = PrometheusMetrics()
        pm.init()
        pm.record_request(model="gpt-4o", tenant="default")

    def test_record_latency_works_after_init(self) -> None:
        pm = PrometheusMetrics()
        pm.init()
        pm.record_latency(model="gpt-4o", seconds=1.5)

    def test_record_tokens_works_after_init(self) -> None:
        pm = PrometheusMetrics()
        pm.init()
        pm.record_tokens(model="gpt-4o", token_type="input", count=50)

    def test_record_error_works_after_init(self) -> None:
        pm = PrometheusMetrics()
        pm.init()
        pm.record_error(error_type="timeout", model="gpt-4o")

    def test_record_guardrail_works_after_init(self) -> None:
        pm = PrometheusMetrics()
        pm.init()
        pm.record_guardrail(rule="prompt_injection")

    def test_record_request_noop_before_init(self) -> None:
        pm = PrometheusMetrics()
        pm.record_request(model="gpt-4o")
