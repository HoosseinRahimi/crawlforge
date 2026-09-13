from typing import Any

from bs4 import BeautifulSoup

REMOVE = [
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "form",
    "nav",
    "footer",
    "aside",
]


def clean_html(html: str) -> tuple[str, dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(REMOVE):
        tag.decompose()
    for tag in soup.find_all(True):
        raw_classes: Any = tag.get("class") or []
        classes = " ".join(str(item) for item in raw_classes) if raw_classes else ""
        marker = f"{classes} {tag.get('id', '')}".lower()
        if any(
            word in marker for word in ("cookie", "advert", "banner", "popup", "modal", "consent")
        ):
            tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup

    def meta_content(attrs: dict[str, Any]) -> str | None:
        node = soup.find("meta", attrs=attrs)
        return str(node.get("content")) if node and node.get("content") else None

    canonical = soup.find("link", rel="canonical")
    metadata: dict[str, object] = {
        "description": meta_content({"name": "description"}),
        "canonical": str(canonical.get("href")) if canonical and canonical.get("href") else None,
        "language": soup.html.get("lang") if soup.html else None,
        "author": meta_content({"name": "author"}),
        "publication_date": meta_content({"property": "article:published_time"}),
    }
    for prop in ("title", "description", "image", "type", "site_name"):
        node = soup.find("meta", property=f"og:{prop}")
        if node and node.get("content"):
            metadata[f"og_{prop}"] = str(node["content"])
    return str(root), metadata
