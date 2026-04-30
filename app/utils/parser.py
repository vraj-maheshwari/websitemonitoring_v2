"""
utils/parser.py
---------------
SaaS-grade HTML parsing intelligence for deep SEO audits.
Guarantees strict defaults and robust extraction.
"""

import re
from collections import Counter
from bs4 import BeautifulSoup


def parse_seo_intelligence(html: str, base_url: str = "") -> dict:
    """
    Highly resilient deep-scan SEO extractor.
    NEVER returns None for list/numeric fields.
    """
    if not html:
        return _empty_seo_report()

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return _empty_seo_report()

    # 1. On-Page Extraction
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    
    meta_desc = ""
    robots_meta = ""
    viewport = False
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").strip().lower()
        if name == "description":
            meta_desc = (meta.get("content") or "").strip()
        elif name == "robots":
            robots_meta = (meta.get("content") or "").strip()
        elif name == "viewport":
            viewport = True

    h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all("h1") if h1.get_text(strip=True)]
    header_tags = {f"h{level}": soup.find_all(f"h{level}") for level in range(2, 7)}
    h2_tags = header_tags["h2"]
    h3_tags = header_tags["h3"]

    # Content & Density
    clean_text = _extract_clean_text(html)
    words = re.findall(r"\w{4,}", clean_text.lower()) 
    stop_words = {"this", "that", "with", "from", "your", "them", "their", "will", "have", "been", "there", "were", "when"}
    filtered_words = [w for w in words if w not in stop_words]
    top_keywords = [k for k, _ in Counter(filtered_words).most_common(5)]

    # 2. Link & Technical Extraction
    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag.get("href") if canonical_tag else ""

    favicon = bool(soup.find("link", rel=re.compile(r"icon", re.I)))
    hreflang = bool(soup.find("link", hreflang=True))
    html_tag = soup.find("html")
    html_lang = html_tag.get("lang") if html_tag else ""

    # 3. Performance & Content Assets
    scripts = soup.find_all("script", src=True)
    links = soup.find_all("link", rel="stylesheet")
    
    js_blocking = 0
    css_blocking = 0
    head = soup.find("head")
    if head:
        js_blocking = len(head.find_all("script", src=True))
        css_blocking = len(head.find_all("link", rel="stylesheet"))

    images = soup.find_all("img")
    missing_alt = sum(1 for img in images if not img.get("alt") or not img.get("alt").strip())

    hyperlinks = soup.find_all("a", href=True)
    internal_count = 0
    external_count = 0
    links_with_anchor_text = 0
    domain = _get_domain(base_url)
    
    for l in hyperlinks:
        if l.get_text(strip=True):
            links_with_anchor_text += 1
        href = l["href"]
        if href.startswith("/") or (domain and domain in href):
            internal_count += 1
        elif href.startswith("http"):
            external_count += 1

    # 4. Mobile & Security Scans
    mixed_content_count = 0
    if base_url.startswith("https:"):
        for tag in soup.find_all(src=True):
            if tag["src"].startswith("http://"):
                mixed_content_count += 1
        for tag in soup.find_all("link", href=True):
            if tag["href"].startswith("http://"):
                mixed_content_count += 1

    mobile_friendly = viewport # Basic heuristic

    img_with_alt = len(images) - missing_alt
    alt_text_coverage = (img_with_alt / len(images)) if images else 1.0
    h_counts = [len(soup.find_all(f"h{level}")) for level in range(1, 7)]
    has_logical_hierarchy = h_counts[0] == 1 and not any(h_counts[i] and not any(h_counts[:i]) for i in range(1, 6))
    has_noindex = "noindex" in robots_meta.lower()

    return {
        "title": title,
        "title_text": title,
        "title_length": len(title),
        "title_present": bool(title),
        "title_in_optimal_range": 50 <= len(title) <= 60,
        "meta_description": meta_desc,
        "meta_description_text": meta_desc,
        "meta_length": len(meta_desc),
        "meta_description_length": len(meta_desc),
        "meta_description_present": bool(meta_desc),
        "meta_description_in_optimal_range": 120 <= len(meta_desc) <= 160,
        "h1_list": h1_tags,
        "h1_text": h1_tags,
        "h1_count": len(h1_tags),
        "h1_present": len(h1_tags) == 1,
        "h2_count": len(h2_tags),
        "h3_count": len(h3_tags),
        "h4_count": len(header_tags["h4"]),
        "h5_count": len(header_tags["h5"]),
        "h6_count": len(header_tags["h6"]),
        "has_logical_hierarchy": has_logical_hierarchy,
        "word_count": len(words),
        "meets_word_count_threshold": len(words) >= 300,
        "keyword_density": top_keywords,
        "image_count": len(images),
        "img_count": len(images),
        "img_with_alt": img_with_alt,
        "img_without_alt": missing_alt,
        "alt_text_coverage": round(alt_text_coverage, 4),
        "missing_alt_count": missing_alt,
        "internal_link_count": internal_count,
        "external_link_count": external_count,
        "links_with_anchor_text": links_with_anchor_text,
        "canonical": canonical,
        "canonical_url": canonical or None,
        "has_canonical": bool(canonical),
        "has_favicon": favicon,
        "has_hreflang": hreflang,
        "hreflang_count": len(soup.find_all("link", hreflang=True)),
        "robots_meta": robots_meta,
        "robots_meta_content": robots_meta or None,
        "has_noindex": has_noindex,
        "html_lang": html_lang,
        "lang_attribute": html_lang or None,
        "has_lang": bool(html_lang),
        "js_blocking_count": js_blocking,
        "css_blocking_count": css_blocking,
        "js_total": len(scripts),
        "css_total": len(links),
        "has_viewport": viewport,
        "mobile_friendly": mobile_friendly,
        "mixed_content_count": mixed_content_count,
        "has_mixed_content": mixed_content_count > 0,
        "page_size_kb": round(len(html) / 1024, 2)
    }


def _extract_clean_text(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return ""


from urllib.parse import urlparse


def _get_domain(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    # netloc includes port (e.g. example.com:8080) which is correct for
    # the `domain in href` internal-link check.
    return parsed.netloc or parsed.path.split("/")[0]


def _empty_seo_report() -> dict:
    return {
        "title": "", "title_length": 0,
        "title_text": "", "title_present": False, "title_in_optimal_range": False,
        "meta_description": "", "meta_length": 0,
        "meta_description_text": "", "meta_description_length": 0,
        "meta_description_present": False, "meta_description_in_optimal_range": False,
        "h1_list": [], "h1_count": 0, "h2_count": 0, "h3_count": 0,
        "h1_text": [], "h1_present": False, "h4_count": 0, "h5_count": 0, "h6_count": 0,
        "has_logical_hierarchy": False, "word_count": 0, "meets_word_count_threshold": False,
        "keyword_density": [], "image_count": 0, "img_count": 0, "img_with_alt": 0,
        "img_without_alt": 0, "alt_text_coverage": 1.0, "missing_alt_count": 0,
        "internal_link_count": 0, "external_link_count": 0, "links_with_anchor_text": 0,
        "canonical": "", "canonical_url": None, "has_canonical": False,
        "has_favicon": False, "has_hreflang": False, "hreflang_count": 0,
        "robots_meta": "", "robots_meta_content": None, "has_noindex": False,
        "html_lang": "", "lang_attribute": None, "has_lang": False,
        "js_blocking_count": 0, "css_blocking_count": 0,
        "js_total": 0, "css_total": 0,
        "has_viewport": False, "mobile_friendly": False,
        "mixed_content_count": 0, "has_mixed_content": False, "page_size_kb": 0.0
    }
