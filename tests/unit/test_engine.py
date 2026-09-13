from types import SimpleNamespace

import pytest

from app.config import Settings
from app.scraper.engine import ScraperEngine
from app.scraper.http_fetcher import FetchedPage
from app.security.url_validation import ValidatedURL


@pytest.mark.asyncio
async def test_auto_mode_falls_back_to_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    from urllib.parse import urlsplit

    import app.scraper.engine as module

    async def fake_validate(url: str) -> ValidatedURL:
        return ValidatedURL(url, urlsplit(url), ("8.8.8.8",))

    async def fake_fetch(*args, **kwargs) -> FetchedPage:
        return FetchedPage(
            "https://public.test",
            200,
            {"content-type": "text/html"},
            '<div id="root"></div><script>x</script>',
        )

    class Browser:
        async def fetch(self, *args, **kwargs):
            return "https://public.test", "<main><h1>Rendered</h1><p>Useful content</p></main>"

    monkeypatch.setattr(module, "validate_url", fake_validate)
    monkeypatch.setattr(module, "fetch_http", fake_fetch)
    monkeypatch.setattr(module, "needs_browser", lambda html: True)
    engine = ScraperEngine(Settings(), SimpleNamespace(fetch=Browser().fetch))
    monkeypatch.setattr(engine.robots, "allowed", lambda *args, **kwargs: _allowed())
    result = await engine.scrape("https://public.test", render_js="auto", outputs=["markdown"])
    assert result.scraping_method == "browser"
    assert "Rendered" in (result.markdown or "")


async def _allowed() -> tuple[bool, float]:
    return True, 0.0
