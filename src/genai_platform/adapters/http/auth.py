from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from genai_platform.adapters.http.dependencies import get_settings
from genai_platform.config import Settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    settings: Settings = Depends(get_settings),
    api_key: str | None = Depends(_api_key_header),
) -> None:
    if not settings.api_keys:
        return
    if not api_key or api_key not in settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
