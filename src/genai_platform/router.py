from fastapi import APIRouter, Depends, Header

from genai_platform.auth import verify_api_key
from genai_platform.dependencies import get_query_service
from genai_platform.schemas import (
    DocumentRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
)
from genai_platform.services import QueryService

v1_router = APIRouter(dependencies=[Depends(verify_api_key)])


async def get_tenant(x_tenant_id: str = Header("default")) -> str:
    return x_tenant_id


@v1_router.post("/query")
async def query(
    request: QueryRequest,
    tenant: str = Depends(get_tenant),
    query_service: QueryService = Depends(get_query_service),
) -> QueryResponse:
    result = await query_service.process_query(
        query=request.query,
        use_cache=request.use_cache,
        max_contexts=request.max_contexts,
        model=request.model,
        tenant=tenant,
    )

    return QueryResponse(
        content=result.content,
        model=result.model,
        from_cache=result.from_cache,
        latency_ms=result.latency_ms,
        tokens_used=result.tokens_used,
        contexts=result.contexts,
        guardrail_triggered=result.guardrail_triggered,
    )


@v1_router.get("/models")
async def list_models(
    query_service: QueryService = Depends(get_query_service),
) -> list[str]:
    s = query_service.settings
    return [s.llm_default_model, *s.llm_fallback_models]


@v1_router.post("/documents", response_model=IngestResponse)
async def ingest_document(
    request: DocumentRequest,
    query_service: QueryService = Depends(get_query_service),
) -> IngestResponse:
    from genai_platform.rag import Document

    doc = Document(
        text=request.text,
        metadata={"source": request.source, **request.metadata},
    )
    doc_id = await query_service.rag.index_document(doc)
    chunks_count = len(query_service.rag.chunker.chunk_document(doc))

    return IngestResponse(
        document_id=doc_id,
        chunks_count=chunks_count,
        message="Document indexé avec succès",
    )
