import pytest

from genai_platform.adapters.llm.litellm_provider import LiteLLMProvider
from genai_platform.adapters.vector_store.qdrant_store import QdrantVectorStore
from genai_platform.config import Settings
from genai_platform.gateway import LLMGateway
from genai_platform.rag import (
    Chunk,
    ChunkingStrategy,
    Document,
    RAGPipeline,
    Reranker,
    ScoredChunk,
)


def _build_rag(settings: Settings, gateway: LLMGateway) -> RAGPipeline:
    return RAGPipeline(
        settings,
        gateway,
        llm_provider=LiteLLMProvider(),
        vector_store=QdrantVectorStore(url=settings.qdrant_url),
    )


class TestChunkingStrategy:
    def setup_method(self) -> None:
        self.chunker = ChunkingStrategy(max_chunk_size=50, overlap=0.1)

    def test_chunk_document_single_paragraph(self) -> None:
        doc = Document(text="Short text.")
        chunks = self.chunker.chunk_document(doc)
        assert len(chunks) == 1
        assert chunks[0].text == "Short text."

    def test_chunk_document_multiple_paragraphs(self) -> None:
        doc = Document(text="First paragraph.\n\nSecond paragraph.\n\nThird.")
        chunks = self.chunker.chunk_document(doc)
        assert len(chunks) >= 3

    def test_chunk_document_splits_long_paragraphs(self) -> None:
        long_text = "Sentence one. " * 20
        doc = Document(text=long_text)
        chunks = self.chunker.chunk_document(doc)
        assert len(chunks) > 1

    def test_chunk_document_adds_overlap(self) -> None:
        chunker = ChunkingStrategy(max_chunk_size=20, overlap=0.5)
        doc = Document(text="Word. " * 10)
        chunks = chunker.chunk_document(doc)
        if len(chunks) > 1:
            assert chunks[1].text.startswith(chunks[0].text[-10:])

    def test_split_by_paragraphs(self) -> None:
        result = self.chunker._split_by_paragraphs("A\n\nB\n\nC")
        assert result == ["A", "B", "C"]

    def test_split_by_sentences(self) -> None:
        result = self.chunker._split_by_sentences("Hello. World! Test?")
        assert len(result) == 3

    def test_detect_section_with_heading(self) -> None:
        result = self.chunker._detect_section("## Introduction")
        assert result == "##"

    def test_detect_section_no_heading(self) -> None:
        result = self.chunker._detect_section("a paragraph.")
        assert result == ""

    def test_add_overlap_single_chunk(self) -> None:
        chunks = [Chunk(text="hello")]
        result = self.chunker._add_overlap(chunks)
        assert len(result) == 1
        assert result[0].text == "hello"


class TestReranker:
    def setup_method(self) -> None:
        self.reranker = Reranker()

    @pytest.mark.asyncio
    async def test_rerank_orders_by_similarity(self) -> None:
        chunks = [
            ScoredChunk(Chunk(text="Python is a programming language"), score=0.5, source="vector"),
            ScoredChunk(Chunk(text="Java is also a language"), score=0.4, source="vector"),
        ]
        result = await self.reranker.rerank("Python", chunks, top_k=5)
        assert result[0].chunk.text == "Python is a programming language"

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(self) -> None:
        chunks = [
            ScoredChunk(Chunk(text=f"Chunk {i}"), score=0.5, source="vector") for i in range(10)
        ]
        result = await self.reranker.rerank("test", chunks, top_k=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_rerank_empty_chunks(self) -> None:
        result = await self.reranker.rerank("test", [], top_k=5)
        assert result == []

    def test_similarity_score_full_match(self) -> None:
        score = self.reranker._similarity_score("python language", "python language")
        assert score == 1.0

    def test_similarity_score_no_match(self) -> None:
        score = self.reranker._similarity_score("python", "java")
        assert score == 0.0

    def test_similarity_score_empty_query(self) -> None:
        score = self.reranker._similarity_score("", "python")
        assert score == 0.0


class TestRAGPipeline:
    def test_init_sets_up_components(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings, llm_provider=LiteLLMProvider())
        rag = _build_rag(settings, gateway)
        assert rag.chunker is not None
        assert rag.reranker is not None
        assert rag.vector_store.ready is False

    @pytest.mark.asyncio
    async def test_initialize_handles_qdrant_unavailable(self) -> None:
        settings = Settings(qdrant_url="http://nonexistent:6333")
        gateway = LLMGateway(settings, llm_provider=LiteLLMProvider())
        rag = _build_rag(settings, gateway)
        await rag.initialize()
        assert rag.vector_store.ready is False

    @pytest.mark.asyncio
    async def test_close_safe_when_not_initialized(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings, llm_provider=LiteLLMProvider())
        rag = _build_rag(settings, gateway)
        await rag.close()

    @pytest.mark.asyncio
    async def test_query_returns_no_documents_response_when_no_collection(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings, llm_provider=LiteLLMProvider())
        rag = _build_rag(settings, gateway)
        await rag.initialize()
        assert rag.vector_store.ready is False
        result = await rag.query("test query")
        assert "Aucun document" in result.content

    @pytest.mark.asyncio
    async def test_index_document_returns_doc_id(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings, llm_provider=LiteLLMProvider())
        rag = _build_rag(settings, gateway)
        doc = Document(text="Test content for indexing.", metadata={"source": "test"})
        doc_id = await rag.index_document(doc)
        assert doc_id is not None
        assert isinstance(doc_id, str)

    @pytest.mark.asyncio
    async def test_index_documents_returns_multiple_ids(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings, llm_provider=LiteLLMProvider())
        rag = _build_rag(settings, gateway)
        docs = [
            Document(text="Doc one.", metadata={"source": "test"}),
            Document(text="Doc two.", metadata={"source": "test"}),
        ]
        doc_ids = await rag.index_documents(docs)
        assert len(doc_ids) == 2

    def test_mock_embedding_returns_consistent_vector(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings, llm_provider=LiteLLMProvider())
        rag = _build_rag(settings, gateway)
        v1 = rag._mock_embedding("hello")
        v2 = rag._mock_embedding("hello")
        assert v1 == v2
        assert len(v1) == 1536

    def test_mock_embedding_different_inputs_different_vectors(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings, llm_provider=LiteLLMProvider())
        rag = _build_rag(settings, gateway)
        v1 = rag._mock_embedding("hello")
        v2 = rag._mock_embedding("world")
        assert v1 != v2

    @pytest.mark.asyncio
    async def test_generate_embedding_falls_back_to_mock(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings, llm_provider=LiteLLMProvider())
        rag = _build_rag(settings, gateway)
        embedding = await rag._generate_embedding("test")
        assert len(embedding) == 1536
        assert all(isinstance(v, float) for v in embedding)

    @pytest.mark.asyncio
    async def test_get_vector_size_returns_1536_on_failure(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings, llm_provider=LiteLLMProvider())
        rag = _build_rag(settings, gateway)
        size = await rag._get_vector_size()
        assert size == 1536
