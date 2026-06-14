import pytest
from fastapi import HTTPException

from genai_platform.auth import verify_api_key
from genai_platform.config import Settings


@pytest.mark.asyncio
async def test_verify_api_key_no_keys_configured() -> None:
    settings = Settings(api_keys=[])
    result = await verify_api_key(settings=settings, api_key=None)
    assert result is None


@pytest.mark.asyncio
async def test_verify_api_key_valid_key() -> None:
    settings = Settings(api_keys=["sk-valid-key"])  # pragma: allowlist secret
    result = await verify_api_key(
        settings=settings, api_key="sk-valid-key"
    )  # pragma: allowlist secret
    assert result is None


@pytest.mark.asyncio
async def test_verify_api_key_invalid_key_raises() -> None:
    settings = Settings(api_keys=["sk-valid-key"])  # pragma: allowlist secret
    with pytest.raises(HTTPException) as exc:
        await verify_api_key(settings=settings, api_key="sk-wrong-key")  # pragma: allowlist secret
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_missing_key_raises() -> None:
    settings = Settings(api_keys=["sk-valid-key"])
    with pytest.raises(HTTPException) as exc:
        await verify_api_key(settings=settings, api_key=None)
    assert exc.value.status_code == 401
