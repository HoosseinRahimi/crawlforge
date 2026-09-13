import pytest

from app.security.url_validation import URLValidationError, validate_url


@pytest.mark.asyncio
async def test_rejects_private_and_unsupported_targets() -> None:
    for value in ("file:///etc/passwd", "ftp://example.com/a", "http://127.0.0.1", "http://[::1]/"):
        with pytest.raises(URLValidationError):
            await validate_url(value)


@pytest.mark.asyncio
async def test_normalizes_public_url_without_fragment() -> None:
    result = await validate_url("https://example.com/path#fragment")
    assert result.value == "https://example.com/path"


@pytest.mark.asyncio
async def test_can_validate_synthetic_url_without_dns() -> None:
    result = await validate_url("https://public.test/a", resolve=False)
    assert result.value == "https://public.test:443/a" or result.value == "https://public.test/a"
