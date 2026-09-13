import time
from dataclasses import dataclass

from app.config import Settings
from app.extractor.cleaner import clean_html
from app.extractor.markdown import to_markdown
from app.observability.metrics import (
    browser_scrapes_total,
    http_scrapes_total,
    scrape_duration_seconds,
    scrapes_total,
)
from app.proxy.manager import ProxyManager
from app.scraper.browser_pool import BrowserPool
from app.scraper.content_detector import needs_browser
from app.scraper.http_fetcher import FetchedPage, FetchError, fetch_http
from app.scraper.robots import RobotsPolicy
from app.security.url_validation import validate_url


@dataclass
class ScrapeOutput:
    url: str
    final_url: str
    status_code: int
    title: str | None
    html: str | None
    markdown: str | None
    metadata: dict[str, object]
    scraping_method: str
    duration_ms: int


class ScraperEngine:
    def __init__(self, settings: Settings, browser_pool: BrowserPool | None = None) -> None:
        self.settings = settings
        self.browser_pool = browser_pool
        self.robots = RobotsPolicy(settings.user_agent, settings.robots_cache_seconds)
        self.proxies = ProxyManager(settings.http_proxy_urls)

    async def scrape(
        self,
        url: str,
        *,
        render_js: bool | str = "auto",
        outputs: list[str] | None = None,
        timeout: int | None = None,
    ) -> ScrapeOutput:
        started = time.perf_counter()
        scrapes_total.labels("sync").inc()
        validated = await validate_url(url)
        allowed, _delay = await self.robots.allowed(validated.value)
        if not allowed:
            raise FetchError("ROBOTS_DENIED", "robots.txt disallows this URL")
        timeout_seconds = timeout or self.settings.scrape_timeout_seconds
        page: FetchedPage | None = None
        method = "http"
        if render_js is not True:
            proxy = self.proxies.next()
            try:
                page = await fetch_http(
                    validated.value,
                    timeout=timeout_seconds,
                    user_agent=self.settings.user_agent,
                    max_bytes=self.settings.max_response_bytes,
                    proxy=proxy,
                )
                self.proxies.report(proxy, True)
                http_scrapes_total.inc()
            except Exception:
                self.proxies.report(proxy, False)
                raise
        if render_js is True or (
            render_js == "auto" and page and page.status_code < 400 and needs_browser(page.html)
        ):
            if not self.browser_pool:
                raise FetchError("BROWSER_UNAVAILABLE", "browser rendering is not configured")
            try:
                final_url, browser_html = await self.browser_pool.fetch(
                    validated.value,
                    timeout_ms=timeout_seconds * 1000,
                    user_agent=self.settings.user_agent,
                )
                await validate_url(final_url)
                page = FetchedPage(final_url, 200, {"content-type": "text/html"}, browser_html)
                method = "browser"
                browser_scrapes_total.inc()
            except Exception as exc:
                raise FetchError("BROWSER_FAILURE", "browser rendering failed") from exc
        assert page is not None
        cleaned, metadata = clean_html(page.html)
        markdown = to_markdown(cleaned)
        from bs4 import BeautifulSoup

        title_node = BeautifulSoup(page.html, "html.parser").title
        title = title_node.get_text(strip=True) if title_node else None
        elapsed = int((time.perf_counter() - started) * 1000)
        scrape_duration_seconds.observe(elapsed / 1000)
        return ScrapeOutput(
            validated.value,
            page.url,
            page.status_code,
            title,
            cleaned if not outputs or "html" in outputs else None,
            markdown if not outputs or "markdown" in outputs else None,
            metadata,
            method,
            elapsed,
        )
