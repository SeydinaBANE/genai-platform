from fastapi import Request

from genai_platform.application.query_service import QueryService
from genai_platform.config import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_query_service(request: Request) -> QueryService:
    return request.app.state.query_service  # type: ignore[no-any-return]
