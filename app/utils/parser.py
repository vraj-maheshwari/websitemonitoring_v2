"""
utils/parser.py
---------------
HTML parsing helpers built on BeautifulSoup.
Kept separate so services stay thin.
"""

from bs4 import BeautifulSoup


def parse_seo_tags(html: str) -> dict:
    """
    Extract basic SEO signals from raw HTML.

    Returns:
        {
            "title":            str | None,
            "meta_description": str | None,
            "has_meta":         bool,
            "has_h1":           bool,
            "h1_text":          str | None,
        }
    """
    if not html:
        return {
            "title": None,
            "meta_description": None,
            "has_meta": False,
            "has_h1": False,
            "h1_text": None,
        }

    soup = BeautifulSoup(html, "lxml")

    # ── <title> ────────────────────────────────────────────────────────────
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None
    if title == "":
        title = None

    # ── <meta name="description"> ──────────────────────────────────────────
    meta_description = None
    for meta_tag in soup.find_all("meta"):
        name_value = (meta_tag.get("name") or "").strip().lower()
        if name_value != "description":
            continue

        content = (meta_tag.get("content") or "").strip()
        meta_description = content or None
        break

    # ── First <h1> ─────────────────────────────────────────────────────────
    h1_tag = soup.find("h1")
    h1_text = h1_tag.get_text(strip=True) if h1_tag else None
    if h1_text == "":
        h1_text = None

    return {
        "title":            title,
        "meta_description": meta_description,
        "has_meta":         bool(meta_description),
        "has_h1":           bool(h1_text),
        "h1_text":          h1_text,
    }
