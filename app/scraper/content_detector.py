from bs4 import BeautifulSoup


def needs_browser(html: str, *, min_text: int = 200) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.get_text(" ").split())
    scripts = len(soup.find_all("script"))
    markers = " ".join(str(x.get("id", "")) for x in soup.find_all(True)).lower()
    shell = any(marker in markers for marker in ("__next", "__nuxt", "app-root", "root"))
    return len(text) < min_text and (scripts >= 3 or shell or not soup.find(["main", "article"]))
