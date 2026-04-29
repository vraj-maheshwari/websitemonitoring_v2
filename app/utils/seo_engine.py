def analyze_seo(signals: dict, ttfb: float | None = None, https_redirect: bool = False) -> dict:
    ttfb = ttfb if ttfb is not None else signals.get("ttfb")
    page_size_kb = float(signals.get("page_size_kb") or 0.0)
    https_redirect = bool(https_redirect or signals.get("https_redirect"))

    on_page = 0
    on_page += 20 if signals.get("title_present") else 0
    on_page += 20 if signals.get("title_in_optimal_range") else 0
    on_page += 20 if signals.get("meta_description_present") else 0
    on_page += 20 if signals.get("meta_description_in_optimal_range") else 0
    on_page += 20 if signals.get("h1_present") else 0

    technical = 0
    technical += 25 if signals.get("has_robots_txt") or signals.get("has_robots") else 0
    technical += 25 if signals.get("has_sitemap_xml") or signals.get("has_sitemap") else 0
    technical += 25 if signals.get("has_canonical") or signals.get("canonical") else 0
    technical += 15 if signals.get("has_lang") or signals.get("html_lang") else 0
    technical += 10 if not signals.get("has_noindex") else 0

    content = 0
    content += 40 if signals.get("meets_word_count_threshold") else 0
    content += 30 if signals.get("has_logical_hierarchy") else 0
    content += round(30 * float(signals.get("alt_text_coverage", 1.0)))

    performance = 0
    if ttfb is not None:
        performance += 50 if ttfb < 0.8 else 30 if ttfb < 1.5 else 0
    if page_size_kb < 500:
        performance += 50
    elif page_size_kb < 1000:
        performance += 35
    performance = min(performance, 100)

    security_mobile = 0
    security_mobile += 40 if https_redirect else 0
    security_mobile += 40 if signals.get("has_viewport") else 0
    security_mobile += 20 if not signals.get("has_mixed_content") and not signals.get("mixed_content_count") else 0

    score = round(
        on_page * 0.40
        + technical * 0.25
        + content * 0.15
        + performance * 0.10
        + security_mobile * 0.10
    )
    score = max(0, min(100, score))
    status = "GOOD" if score >= 80 else "FAIR" if score >= 60 else "POOR"

    issues = _build_issues(signals, ttfb, page_size_kb, https_redirect)
    recommendations = sorted(_build_recommendations(signals, issues), key=lambda item: item["priority"])

    return {
        "score": score,
        "status": status,
        "breakdown": {
            "on_page": on_page,
            "technical": technical,
            "content": content,
            "performance": performance,
            "security_mobile": security_mobile,
        },
        "issues": issues,
        "recommendations": recommendations,
    }


def _issue(check: str, category: str, message: str, impact: str) -> dict:
    return {"check": check, "category": category, "message": message, "impact": impact}


def _build_issues(signals: dict, ttfb: float | None, page_size_kb: float, https_redirect: bool) -> list[dict]:
    issues = []
    if not signals.get("title_present"):
        issues.append(_issue("title_present", "on_page", "Missing page title.", "high"))
    elif not signals.get("title_in_optimal_range"):
        issues.append(_issue("title_length", "on_page", "Title should be 50-60 characters.", "medium"))
    if not signals.get("meta_description_present"):
        issues.append(_issue("meta_description_present", "on_page", "Missing meta description.", "high"))
    elif not signals.get("meta_description_in_optimal_range"):
        issues.append(_issue("meta_description_length", "on_page", "Meta description should be 120-160 characters.", "medium"))
    if not signals.get("h1_present"):
        issues.append(_issue("h1_present", "content", "Page should have exactly one H1.", "high"))
    if not signals.get("meets_word_count_threshold"):
        issues.append(_issue("word_count", "content", "Visible content is below 300 words.", "medium"))
    if signals.get("img_without_alt", signals.get("missing_alt_count", 0)):
        issues.append(_issue("alt_text_coverage", "content", "Some images are missing alt text.", "medium"))
    if not signals.get("has_robots_txt") and not signals.get("has_robots"):
        issues.append(_issue("has_robots_txt", "technical", "robots.txt was not found.", "low"))
    if not signals.get("has_sitemap_xml") and not signals.get("has_sitemap"):
        issues.append(_issue("has_sitemap_xml", "technical", "sitemap.xml was not found.", "medium"))
    if signals.get("has_noindex"):
        issues.append(_issue("has_noindex", "technical", "Robots meta includes noindex.", "high"))
    if ttfb is not None and ttfb >= 1.5:
        issues.append(_issue("ttfb", "performance", "TTFB is slower than 1.5 seconds.", "medium"))
    if page_size_kb >= 1000:
        issues.append(_issue("page_size_kb", "performance", "HTML response is larger than 1 MB.", "low"))
    if not https_redirect:
        issues.append(_issue("https_redirect", "security_mobile", "HTTPS redirect was not detected.", "medium"))
    if signals.get("has_mixed_content") or signals.get("mixed_content_count", 0):
        issues.append(_issue("has_mixed_content", "security_mobile", "Mixed HTTP content detected.", "high"))
    if not signals.get("has_viewport"):
        issues.append(_issue("has_viewport", "security_mobile", "Missing mobile viewport meta tag.", "medium"))
    return issues


def _build_recommendations(signals: dict, issues: list[dict]) -> list[dict]:
    actions = {
        "title_present": (1, "Add a page title", "Write a unique title that describes the primary page intent."),
        "title_length": (3, "Tune the title length", "Keep the title close to 50-60 characters."),
        "meta_description_present": (2, "Add a meta description", "Write a 120-160 character description that summarizes the page."),
        "meta_description_length": (4, "Tune the meta description", "Keep descriptions concise enough for search result snippets."),
        "h1_present": (1, "Fix H1 structure", "Use exactly one clear H1 near the top of the page."),
        "word_count": (5, "Expand visible content", "Add useful, crawlable copy until the page has at least 300 words."),
        "alt_text_coverage": (6, "Add image alt text", "Describe meaningful images with concise alt attributes."),
        "has_robots_txt": (8, "Publish robots.txt", "Add /robots.txt with crawl rules and sitemap discovery."),
        "has_sitemap_xml": (7, "Publish sitemap.xml", "Expose canonical URLs in /sitemap.xml."),
        "has_noindex": (1, "Remove accidental noindex", "Remove noindex unless this page should be hidden from search."),
        "ttfb": (5, "Reduce TTFB", "Review server latency, caching, database calls, and CDN configuration."),
        "page_size_kb": (9, "Reduce response size", "Trim server-rendered HTML and defer non-critical payload."),
        "https_redirect": (4, "Enforce HTTPS", "Redirect HTTP traffic to HTTPS at the edge or web server."),
        "has_mixed_content": (2, "Remove mixed content", "Serve all scripts, styles, images, and links over HTTPS."),
        "has_viewport": (6, "Add viewport meta", "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">."),
    }
    recommendations = []
    for issue in issues:
        priority, action, detail = actions.get(issue["check"], (10, "Review SEO issue", issue["message"]))
        recommendations.append({"priority": priority, "action": action, "detail": detail})
    return recommendations
