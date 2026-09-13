import asyncio
from collections import deque
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.crawler.url_normalizer import normalize_url
from app.scraper.engine import ScrapeOutput, ScraperEngine


class Crawler:
    def __init__(self, engine: ScraperEngine, *, concurrency: int = 5, delay: float = 0.5) -> None:
        self.engine = engine
        self.concurrency = concurrency
        self.delay = delay

    async def crawl(
        self, start_url: str, *, max_depth: int, max_pages: int, allow_external: bool
    ) -> list[ScrapeOutput]:
        start = normalize_url(start_url)
        root_host = __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(start).hostname
        seen = {start}
        frontier: deque[tuple[str, int]] = deque([(start, 0)])
        results: list[ScrapeOutput] = []
        while frontier and len(results) < max_pages:
            level: list[tuple[str, int]] = []
            while frontier and len(level) < max_pages - len(results):
                level.append(frontier.popleft())
            semaphore = asyncio.Semaphore(self.concurrency)

            async def visit(
                item: tuple[str, int], gate: asyncio.Semaphore = semaphore
            ) -> tuple[ScrapeOutput | None, list[str]]:
                url, depth = item
                async with gate:
                    try:
                        result = await self.engine.scrape(
                            url, render_js="auto", outputs=["markdown", "html"]
                        )
                        await asyncio.sleep(self.delay)
                    except Exception:
                        return None, []
                if depth >= max_depth or not result.html:
                    return result, []
                soup = BeautifulSoup(result.html, "html.parser")
                links: list[str] = []
                for anchor in soup.find_all("a", href=True):
                    candidate = normalize_url(urljoin(result.final_url, str(anchor["href"])))
                    from urllib.parse import urlsplit

                    parsed = urlsplit(candidate)
                    if parsed.scheme not in {"http", "https"}:
                        continue
                    if not allow_external and parsed.hostname != root_host:
                        continue
                    links.append(candidate)
                return result, links

            visited = await asyncio.gather(*(visit(item) for item in level))
            for result, links in visited:
                if result:
                    results.append(result)
                for link in links:
                    if link not in seen and len(seen) < max_pages:
                        seen.add(link)
                        frontier.append((link, level[0][1] + 1))
        return results[:max_pages]
