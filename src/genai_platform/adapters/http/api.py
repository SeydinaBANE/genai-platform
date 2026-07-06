from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from genai_platform import bootstrap
from genai_platform.adapters.http.router import v1_router
from genai_platform.config import Settings
from genai_platform.domain.rate_limiting import RateLimiter
from genai_platform.logging import setup_logging

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    setup_logging(settings.log_level)
    components = await bootstrap.build_app_components(settings)
    app.state.settings = components.settings
    app.state.query_service = components.query_service
    app.state.rate_limiter = components.rate_limiter
    yield
    await components.rag.close()


app = FastAPI(
    title="GenAI Platform",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_type": type(exc).__name__},
    )


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next: Any) -> Any:
    if request.url.path == "/metrics":
        return await call_next(request)
    rate_limiter: RateLimiter = request.app.state.rate_limiter
    client_key = request.client.host if request.client else "unknown"
    if not rate_limiter.check(client_key):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
        )
    rate_limiter.consume(client_key)
    return await call_next(request)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "version": settings.app_version}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/metrics")
async def metrics() -> Any:
    from fastapi.responses import Response
    from prometheus_client import generate_latest

    return Response(content=generate_latest(), media_type="text/plain")
