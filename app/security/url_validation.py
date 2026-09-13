import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit


class URLValidationError(ValueError):
    pass


def _safe_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip.is_global and not ip.is_unspecified and not ip.is_multicast


async def resolve_public(host: str, port: int) -> list[str]:
    try:
        infos = await asyncio.get_running_loop().run_in_executor(
            None, lambda: socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        )
    except socket.gaierror as exc:
        raise URLValidationError("DNS resolution failed") from exc
    addresses = sorted({str(item[4][0]) for item in infos})
    if not addresses or any(not _safe_ip(address) for address in addresses):
        raise URLValidationError("target resolves to a non-public address")
    return addresses


@dataclass(frozen=True)
class ValidatedURL:
    value: str
    parsed: SplitResult
    addresses: tuple[str, ...]


async def validate_url(raw: str, *, resolve: bool = True) -> ValidatedURL:
    parsed = urlsplit(raw.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise URLValidationError("only http and https URLs are supported")
    if not parsed.hostname or parsed.username or parsed.password:
        raise URLValidationError("URL must contain a hostname and no credentials")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise URLValidationError("invalid URL port") from exc
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "ip6-localhost", "metadata.google.internal"}:
        raise URLValidationError("local and metadata hosts are blocked")
    normalized = urlunsplit(
        (
            parsed.scheme.lower(),
            host + (f":{port}" if parsed.port else ""),
            parsed.path or "/",
            parsed.query,
            "",
        )
    )
    addresses = tuple(await resolve_public(host, port)) if resolve and not _safe_ip(host) else ()
    if _safe_ip(host) is False and not addresses and resolve:
        raise URLValidationError("target is not publicly reachable")
    if _safe_ip(host) is True:
        addresses = (host,)
    return ValidatedURL(normalized, urlsplit(normalized), addresses)
