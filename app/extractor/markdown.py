from markdownify import markdownify


def to_markdown(html: str) -> str:
    return str(markdownify(html, heading_style="ATX", bullets="-")).strip()
