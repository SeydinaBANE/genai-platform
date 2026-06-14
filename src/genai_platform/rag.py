import hashlib
import uuid
from typing import Any

from genai_platform.config import Settings
from genai_platform.gateway import LLMGateway


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


class ChunkingStrategy:
    def __init__(self, max_chunk_size: int = 512, overlap: float = 0.1) -> None:
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk_document(self, document: Document) -> list[Chunk]:
        text = document.text
        chunks: list[Chunk] = []
        paragraphs = self._split_by_paragraphs(text)

        for para in paragraphs:
            if len(para) > self.max_chunk_size:
                sentences = self._split_by_sentences(para)
                chunks.extend(self._group_sentences(sentences))
            else:
                chunks.append(
                    Chunk(
                        text=para,
                        metadata={**document.metadata, "section": self._detect_section(para)},
                    )
                )

        chunks = self._add_overlap(chunks)
        return chunks

    def _split_by_paragraphs(self, text: str) -> list[str]:
        return [p.strip() for p in text.split("\n\n") if p.strip()]

    def _split_by_sentences(self, text: str) -> list[str]:
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _group_sentences(self, sentences: list[str]) -> list[Chunk]:
        chunks: list[Chunk] = []
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) > self.max_chunk_size:
                if current:
                    chunks.append(Chunk(text=current.strip()))
                current = sentence
            else:
                current += " " + sentence
        if current:
            chunks.append(Chunk(text=current.strip()))
        return chunks

    def _add_overlap(self, chunks: list[Chunk]) -> list[Chunk]:
        if len(chunks) <= 1:
            return chunks
        overlap_size = int(self.max_chunk_size * self.overlap)
        result: list[Chunk] = []
        for i, chunk in enumerate(chunks):
            if i > 0 and overlap_size > 0:
                prev_end = chunks[i - 1].text[-overlap_size:]
                chunk = Chunk(
                    text=prev_end + " " + chunk.text,
                    metadata=chunk.metadata,
                )
            result.append(chunk)
        return result

    def _detect_section(self, text: str) -> str:
        import re

        match = re.match(r"^(#{1,3}|[A-Z][^.]{0,50})", text.strip())
        return match.group(1) if match else ""


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


class RAGPipeline:
    def __init__(self, settings: Settings, gateway: LLMGateway) -> None:
        self.settings = settings
        self.gateway = gateway
        self.chunker = ChunkingStrategy(
            max_chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        )
        self.reranker = Reranker(model=settings.rag_rerank_model)
        self._qdrant_client: Any = None
        self._collection_ready = False

    async def initialize(self) -> None:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import Distance, VectorParams

        self._qdrant_client = AsyncQdrantClient(url=self.settings.qdrant_url)
        try:
            collections = await self._qdrant_client.get_collections()
            exists = any(
                c.name == self.settings.rag_collection_name for c in collections.collections
            )
            if not exists:
                vector_size = await self._get_vector_size()
                await self._qdrant_client.create_collection(
                    collection_name=self.settings.rag_collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
            self._collection_ready = True
        except Exception:
            self._collection_ready = False

    async def close(self) -> None:
        if self._qdrant_client:
            await self._qdrant_client.close()
            self._qdrant_client = None
            self._collection_ready = False

    async def _get_vector_size(self) -> int:
        try:
            v = await self._generate_embedding("test")
            return len(v)
        except Exception:
            return 1536

    async def _generate_embedding(self, text: str) -> list[float]:
        try:
            from litellm import aembedding

            response = await aembedding(
                model=self.settings.rag_embedding_model,
                input=[text],
            )
            return response.data[0]["embedding"]  # type: ignore[no-any-return]
        except Exception:
            return self._mock_embedding(text)

    def _mock_embedding(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        rng = __import__("random").Random(seed)
        return [rng.random() for _ in range(1536)]

    async def index_documents(self, documents: list[Document]) -> list[str]:
        doc_ids: list[str] = []
        for doc in documents:
            doc_id = await self.index_document(doc)
            doc_ids.append(doc_id)
        return doc_ids

    async def index_document(self, document: Document) -> str:
        from qdrant_client.models import PointStruct

        chunks = self.chunker.chunk_document(document)
        doc_id = str(uuid.uuid4())
        vectors = await self._generate_embeddings([c.text for c in chunks])

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=v,
                payload={
                    "text": c.text,
                    "doc_id": doc_id,
                    "source": document.metadata.get("source", "unknown"),
                    "chunk_index": i,
                },
            )
            for i, (c, v) in enumerate(zip(chunks, vectors, strict=True))
        ]

        if self._qdrant_client and self._collection_ready:
            await self._qdrant_client.upsert(
                collection_name=self.settings.rag_collection_name,
                points=points,
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

        if self._qdrant_client and self._collection_ready:
            results = await self._qdrant_client.search(
                collection_name=self.settings.rag_collection_name,
                query_vector=query_vector,
                limit=self.settings.rag_top_k,
            )
            contexts = [
                ScoredChunk(
                    chunk=Chunk(
                        text=r.payload.get("text", ""),
                        metadata={"source": r.payload.get("source", "unknown")},
                    ),
                    score=r.score,
                    source="vector",
                )
                for r in results
            ]

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
