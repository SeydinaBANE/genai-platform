class Chunk:
    def __init__(self, text: str, metadata: dict[str, str] | None = None) -> None:
        self.text = text
        self.metadata = metadata or {}


class Document:
    def __init__(self, text: str, metadata: dict[str, str] | None = None) -> None:
        self.text = text
        self.metadata = metadata or {}


class ScoredChunk:
    def __init__(self, chunk: Chunk, score: float, source: str = "vector") -> None:
        self.chunk = chunk
        self.score = score
        self.source = source


class RAGResult:
    def __init__(
        self,
        content: str,
        model: str,
        latency_ms: int,
        tokens_prompt: int,
        tokens_completion: int,
        from_fallback: bool,
        contexts: list[str],
        sources: list[str],
    ) -> None:
        self.content = content
        self.model = model
        self.latency_ms = latency_ms
        self.tokens_prompt = tokens_prompt
        self.tokens_completion = tokens_completion
        self.from_fallback = from_fallback
        self.contexts = contexts
        self.sources = sources


class LLMResponse:
    def __init__(
        self,
        content: str,
        model: str,
        latency_ms: int,
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
        from_fallback: bool = False,
    ) -> None:
        self.content = content
        self.model = model
        self.latency_ms = latency_ms
        self.tokens_prompt = tokens_prompt
        self.tokens_completion = tokens_completion
        self.from_fallback = from_fallback


class GuardrailResult:
    def __init__(
        self,
        blocked: bool,
        sanitized_text: str | None = None,
        reason: str | None = None,
        triggered_rules: list[str] | None = None,
    ):
        self.blocked = blocked
        self.sanitized_text = sanitized_text
        self.reason = reason
        self.triggered_rules = triggered_rules or []
