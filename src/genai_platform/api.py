from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from genai_platform.config import Settings
from genai_platform.router import v1_router

settings = Settings()

app = FastAPI(
    title="GenAI Platform",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "version": settings.app_version}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
