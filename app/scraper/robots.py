import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from protego import Protego


@dataclass
class RobotsEntry:
    parser: Protego | None
    fetched_at: float
    denied_on_error: bool = False


class RobotsPolicy:
    def __init__(self, user_agent: str, cache_seconds: int = 3600) -> None:
        self.user_agent = user_agent
        self.cache_seconds = cache_seconds
        self._cache: dict[str, RobotsEntry] = {}

    async def allowed(self, url: str, *, timeout: float = 10) -> tuple[bool, float]:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        entry = self._cache.get(origin)
        if not entry or time.monotonic() - entry.fetched_at > self.cache_seconds:
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                    response = await client.get(
                        f"{origin}/robots.txt", headers={"User-Agent": self.user_agent}
                    )
                if response.status_code in {404, 410}:
                    entry = RobotsEntry(None, time.monotonic())
                elif response.status_code >= 500:
                    entry = RobotsEntry(None, time.monotonic(), denied_on_error=True)
                else:
                    entry = RobotsEntry(Protego.parse(response.text), time.monotonic())
            except httpx.HTTPError:
                entry = RobotsEntry(None, time.monotonic(), denied_on_error=True)
            self._cache[origin] = entry
        if entry.denied_on_error:
            return False, 0.0
        if entry.parser is None:
            return True, 0.0
        return entry.parser.can_fetch(self.user_agent, url), float(
            entry.parser.crawl_delay(self.user_agent) or 0
        )
