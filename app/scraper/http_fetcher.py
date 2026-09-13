import asyncio
from dataclasses import dataclass

import httpx

from app.security.url_validation import URLValidationError, validate_url


@dataclass(frozen=True)
class FetchedPage:
    url: str
    status_code: int
    headers: dict[str, str]
    html: str


class FetchError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


async def fetch_http(
    url: str, *, timeout: float, user_agent: str, max_bytes: int, proxy: str | None = None
) -> FetchedPage:
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    transport = httpx.AsyncHTTPTransport(retries=0)
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"},
            limits=limits,
            transport=transport,
            proxy=proxy,
        ) as client:
            current = url
            for _ in range(6):
                attempts = 0
                while True:
                    attempts += 1
                    try:
                        response = await client.get(current)
                    except httpx.TimeoutException as exc:
                        if attempts < 3:
                            await asyncio.sleep(0.2 * 2 ** (attempts - 1))
                            continue
                        raise FetchError("SCRAPE_TIMEOUT", "target page timed out") from exc
                    except httpx.RequestError as exc:
                        if attempts < 3:
                            await asyncio.sleep(0.2 * 2 ** (attempts - 1))
                            continue
                        raise FetchError(
                            "DNS_OR_NETWORK_FAILURE", "target page could not be fetched"
                        ) from exc
                    if response.status_code in {502, 503, 504} and attempts < 3:
                        await asyncio.sleep(0.2 * 2 ** (attempts - 1))
                        continue
                    break
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        break
                    from urllib.parse import urljoin

                    try:
                        current = (await validate_url(urljoin(current, location))).value
                    except URLValidationError as exc:
                        raise FetchError("SSRF_BLOCKED", "redirect target was blocked") from exc
                    continue
                if response.status_code >= 400:
                    raise FetchError("HTTP_ERROR", f"target returned HTTP {response.status_code}")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise FetchError(
                            "RESPONSE_TOO_LARGE", "response exceeded the configured size limit"
                        )
                return FetchedPage(
                    current,
                    response.status_code,
                    dict(response.headers),
                    body.decode(response.encoding or "utf-8", errors="replace"),
                )
            raise FetchError("TOO_MANY_REDIRECTS", "target exceeded redirect limit")
    finally:
        await transport.aclose()
