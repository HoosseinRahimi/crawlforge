from app.crawler.url_normalizer import normalize_url
from app.extractor.cleaner import clean_html
from app.extractor.markdown import to_markdown
from app.scraper.content_detector import needs_browser


def test_url_normalization_removes_fragment_and_default_port() -> None:
    assert normalize_url("HTTP://Example.COM:80/docs/#top") == "http://example.com/docs"


def test_cleaner_removes_ui_and_extracts_metadata() -> None:
    html = (
        '<html lang="en"><head><title>Article</title><meta name="description" content="desc">'
        "</head><body><nav>Menu</nav><main><h1>Hello</h1><p>World</p></main>"
        "<script>x()</script></body></html>"
    )
    cleaned, metadata = clean_html(html)
    assert "Menu" not in cleaned and "script" not in cleaned
    assert metadata["description"] == "desc"
    assert "# Hello" in to_markdown(cleaned)


def test_js_shell_is_detected() -> None:
    assert needs_browser(
        '<div id="root"></div><script src="a"></script><script src="b"></script>'
        '<script src="c"></script>'
    )
