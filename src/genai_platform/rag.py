import uuid

from genai_platform.config import Settings
from genai_platform.domain.chunking import ChunkingStrategy
from genai_platform.domain.embeddings import mock_embedding
from genai_platform.domain.models import Chunk, Document, RAGResult, ScoredChunk
from genai_platform.domain.reranking import Reranker
from genai_platform.gateway import LLMGateway
from genai_platform.ports.llm_provider import LLMProviderPort
from genai_platform.ports.vector_store import VectorStorePort

__all__ = [
    "Chunk",
    "ChunkingStrategy",
    "Document",
    "RAGPipeline",
    "RAGResult",
    "Reranker",
    "ScoredChunk",
]


class RAGPipeline:
    def __init__(
        self,
        settings: Settings,
        gateway: LLMGateway,
        llm_provider: LLMProviderPort,
        vector_store: VectorStorePort,
    ) -> None:
        self.settings = settings
        self.gateway = gateway
        self.llm_provider = llm_provider
        self.vector_store = vector_store
        self.chunker = ChunkingStrategy(
            max_chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        )
        self.reranker = Reranker(model=settings.rag_rerank_model)

    async def initialize(self) -> None:
        vector_size = await self._get_vector_size()
        await self.vector_store.ensure_collection(self.settings.rag_collection_name, vector_size)

    async def close(self) -> None:
        await self.vector_store.close()

    async def _get_vector_size(self) -> int:
        try:
            v = await self._generate_embedding("test")
            return len(v)
        except Exception:
            return 1536

    async def _generate_embedding(self, text: str) -> list[float]:
        try:
            return await self.llm_provider.embed(model=self.settings.rag_embedding_model, text=text)
        except Exception:
            return self._mock_embedding(text)

    def _mock_embedding(self, text: str) -> list[float]:
        return mock_embedding(text)

    async def index_documents(self, documents: list[Document]) -> list[str]:
        doc_ids: list[str] = []
        for doc in documents:
            doc_id = await self.index_document(doc)
            doc_ids.append(doc_id)
        return doc_ids

    async def index_document(self, document: Document) -> str:
        chunks = self.chunker.chunk_document(document)
        doc_id = str(uuid.uuid4())
        vectors = await self._generate_embeddings([c.text for c in chunks])

        await self.vector_store.upsert(
            collection=self.settings.rag_collection_name,
            doc_id=doc_id,
            chunks=chunks,
            vectors=vectors,
            source=document.metadata.get("source", "unknown"),
        )

        return doc_id

    async def _generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [await self._generate_embedding(t) for t in texts]

    async def query(
        self, query: str, top_k: int | None = None, model: str | None = None
    ) -> "RAGResult":
        top_k = top_k or self.settings.rag_rerank_top_k

        query_vector = await self._generate_embedding(query)
        contexts: list[ScoredChunk] = []

        if self.vector_store.ready:
            contexts = await self.vector_store.search(
                collection=self.settings.rag_collection_name,
                query_vector=query_vector,
                limit=self.settings.rag_top_k,
            )

        if not contexts:
            return RAGResult(
                content="Aucun document trouvé dans la base de connaissances.",
                model=self.settings.llm_default_model,
                latency_ms=0,
                tokens_prompt=0,
                tokens_completion=0,
                from_fallback=False,
                contexts=[],
                sources=[],
            )

        reranked = await self.reranker.rerank(query, contexts, top_k=top_k)
        context_text = "\n\n".join(f"[{i + 1}] {c.chunk.text}" for i, c in enumerate(reranked))

        prompt = (
            f"Tu es un assistant expert spécialisé dans la réponse aux questions "
            f"basées sur les documents fournis.\n\n"
            f"Règles :\n"
            f"1. Réponds UNIQUEMENT en te basant sur le contexte fourni.\n"
            f"2. Si la réponse ne se trouve pas dans le contexte, dis "
            f"'Je ne trouve pas cette information dans les documents fournis.'\n"
            f"3. Cite tes sources avec le numéro de document : [1], [2], etc.\n"
            f"4. Utilise un langage clair et professionnel.\n\n"
            f"Contexte :\n{context_text}\n\n"
            f"Question : {query}"
        )

        llm_response = await self.gateway.complete(
            prompt=prompt,
            model=model,
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
        )

        return RAGResult(
            content=llm_response.content,
            model=llm_response.model,
            latency_ms=llm_response.latency_ms,
            tokens_prompt=llm_response.tokens_prompt,
            tokens_completion=llm_response.tokens_completion,
            from_fallback=llm_response.from_fallback,
            contexts=[c.chunk.text for c in reranked],
            sources=list(
                {c.chunk.metadata.get("source", "unknown") for c in reranked if c.chunk.metadata}
            ),
        )
