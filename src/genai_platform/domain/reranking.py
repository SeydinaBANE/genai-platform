from genai_platform.domain.models import ScoredChunk


class Reranker:
    def __init__(self, model: str = "cohere/rerank-v3.5") -> None:
        self.model = model

    async def rerank(
        self, query: str, chunks: list[ScoredChunk], top_k: int = 5
    ) -> list[ScoredChunk]:
        scored = []
        for chunk in chunks:
            score = self._similarity_score(query, chunk.chunk.text)
            scored.append(
                ScoredChunk(
                    chunk=chunk.chunk,
                    score=score,
                    source="reranker",
                )
            )
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    def _similarity_score(self, query: str, text: str) -> float:
        query_tokens = set(query.lower().split())
        text_tokens = set(text.lower().split())
        if not query_tokens or not text_tokens:
            return 0.0
        intersection = query_tokens & text_tokens
        return len(intersection) / max(len(query_tokens), 1)
