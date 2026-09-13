import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright


class BrowserPool:
    def __init__(self, size: int = 4) -> None:
        self.size = size
        self._semaphore = asyncio.Semaphore(size)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None

    @asynccontextmanager
    async def context(self, *, timeout_ms: int = 30_000) -> AsyncIterator[BrowserContext]:
        if not self._browser:
            await self.start()
        assert self._browser
        async with self._semaphore:
            context = await self._browser.new_context()
            context.set_default_timeout(timeout_ms)
            try:
                yield context
            finally:
                await context.close()

    async def fetch(self, url: str, *, timeout_ms: int, user_agent: str) -> tuple[str, str]:
        async with self.context(timeout_ms=timeout_ms) as context:
            await context.set_extra_http_headers({"User-Agent": user_agent})

            async def guard(route) -> None:
                from app.security.url_validation import URLValidationError, validate_url

                try:
                    await validate_url(route.request.url)
                except URLValidationError:
                    await route.abort("blockedbyclient")
                    return
                await route.continue_()

            await context.route("**/*", guard)
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 10_000))
            return page.url, await page.content()
