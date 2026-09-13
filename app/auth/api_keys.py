import hashlib
import hmac
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import APIKey
from app.db.session import get_session


def digest_key(raw: str) -> bytes:
    pepper = get_settings().api_key_pepper.get_secret_value().encode()
    return hmac.new(pepper, raw.encode(), hashlib.sha256).digest()


def generate_key() -> tuple[str, str, bytes]:
    prefix = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
    raw = f"crawl_{prefix}_{secrets.token_urlsafe(32)}"
    return raw, prefix, digest_key(raw)


async def require_api_key(
    authorization: str | None = Header(default=None), session: AsyncSession = Depends(get_session)
) -> APIKey:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "bearer API key required"},
        )
    raw = authorization[7:].strip()
    prefix = (
        raw.split("_", 2)[1] if raw.startswith("crawl_") and len(raw.split("_", 2)) == 3 else ""
    )
    key = (
        await session.execute(
            select(APIKey).where(APIKey.prefix == prefix, APIKey.active.is_(True))
        )
    ).scalar_one_or_none()
    if not key or not hmac.compare_digest(key.digest, digest_key(raw)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_API_KEY", "message": "invalid API key"},
        )
    return key
