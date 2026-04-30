"""
utils/tech_profiler.py
-----------------------
Detects the technology stack a website is using from HTTP response
headers and HTML source. Returns a structured dict of detected technologies
grouped by category.

Detection is purely passive — no extra requests beyond the main page fetch.
"""

import re
from typing import Any

# ---------------------------------------------------------------------------
# Signature database
# Each entry: (category, name, match_fn)
# match_fn receives (html_lower: str, headers: dict[str, str]) -> bool
# ---------------------------------------------------------------------------

def _h(headers: dict, key: str) -> str:
    """Case-insensitive header lookup, returns empty string if missing."""
    return headers.get(key.lower(), headers.get(key, ""))


_SIGNATURES: list[tuple[str, str, Any]] = [
    # ── JavaScript Frameworks ──────────────────────────────────────────────
    ("js_framework", "React",
     lambda h, hd: "__react" in h or "react-root" in h or "_reactfiber" in h
                   or "data-reactroot" in h or "/react." in h or "react.production" in h),

    ("js_framework", "Next.js",
     lambda h, hd: "__next" in h or "/_next/static" in h or "next/dist" in h),

    ("js_framework", "Vue.js",
     lambda h, hd: "vue.min.js" in h or "/vue." in h or "__vue__" in h
                   or "data-v-" in h or "vue.runtime" in h),

    ("js_framework", "Nuxt.js",
     lambda h, hd: "/_nuxt/" in h or "__nuxt" in h),

    ("js_framework", "Angular",
     lambda h, hd: "ng-version=" in h or "angular.min.js" in h or "/angular." in h
                   or "ng-app" in h or "_nghost" in h),

    ("js_framework", "Svelte",
     lambda h, hd: "svelte" in h and ("__svelte" in h or ".svelte-" in h)),

    ("js_framework", "Ember.js",
     lambda h, hd: "ember.min.js" in h or "ember-application" in h),

    ("js_framework", "Alpine.js",
     lambda h, hd: "x-data=" in h or "alpine.js" in h or "alpinejs" in h),

    ("js_framework", "jQuery",
     lambda h, hd: "jquery.min.js" in h or "jquery.js" in h or "/jquery-" in h),

    ("js_framework", "HTMX",
     lambda h, hd: "htmx.org" in h or "hx-get=" in h or "hx-post=" in h),

    # ── CMS / Site Builders ────────────────────────────────────────────────
    ("cms", "WordPress",
     lambda h, hd: "/wp-content/" in h or "/wp-includes/" in h or "wp-json" in h),

    ("cms", "Shopify",
     lambda h, hd: "cdn.shopify.com" in h or "shopify.com/s/files" in h
                   or _h(hd, "x-shopid") != ""),

    ("cms", "Wix",
     lambda h, hd: "static.wixstatic.com" in h or "wix.com" in h),

    ("cms", "Squarespace",
     lambda h, hd: "squarespace.com" in h or "static1.squarespace.com" in h),

    ("cms", "Webflow",
     lambda h, hd: "webflow.com" in h or _h(hd, "x-powered-by").lower() == "webflow"),

    ("cms", "Ghost",
     lambda h, hd: "ghost.io" in h or "/ghost/api/" in h or "content-api.ghost.org" in h),

    ("cms", "Drupal",
     lambda h, hd: "drupal.js" in h or "/sites/default/files/" in h
                   or _h(hd, "x-generator").lower().startswith("drupal")),

    ("cms", "Joomla",
     lambda h, hd: "/media/jui/" in h or "joomla!" in h),

    ("cms", "HubSpot",
     lambda h, hd: "js.hs-scripts.com" in h or "hubspot.com" in h),

    # ── CDN / Hosting ──────────────────────────────────────────────────────
    ("cdn", "Cloudflare",
     lambda h, hd: _h(hd, "cf-ray") != "" or _h(hd, "server").lower() == "cloudflare"
                   or "cdnjs.cloudflare.com" in h or "cdn.cloudflare.com" in h),

    ("cdn", "Fastly",
     lambda h, hd: _h(hd, "x-served-by").startswith("cache-") or _h(hd, "x-fastly-request-id") != ""),

    ("cdn", "AWS CloudFront",
     lambda h, hd: _h(hd, "x-amz-cf-id") != "" or _h(hd, "via").lower().find("cloudfront") != -1),

    ("cdn", "Vercel",
     lambda h, hd: _h(hd, "x-vercel-id") != "" or _h(hd, "server").lower() == "vercel"),

    ("cdn", "Netlify",
     lambda h, hd: _h(hd, "x-nf-request-id") != "" or _h(hd, "server").lower() == "netlify"),

    ("cdn", "GitHub Pages",
     lambda h, hd: _h(hd, "server").lower() == "github.com"),

    # ── Web Servers ────────────────────────────────────────────────────────
    ("server", "Nginx",
     lambda h, hd: _h(hd, "server").lower().startswith("nginx")),

    ("server", "OpenResty",
     lambda h, hd: _h(hd, "server").lower().startswith("openresty")),

    ("server", "Apache",
     lambda h, hd: _h(hd, "server").lower().startswith("apache")),

    ("server", "Caddy",
     lambda h, hd: _h(hd, "server").lower().startswith("caddy")),

    ("server", "LiteSpeed",
     lambda h, hd: _h(hd, "server").lower().startswith("litespeed")),

    ("server", "IIS",
     lambda h, hd: _h(hd, "server").lower().startswith("microsoft-iis")),

    # ── Analytics ─────────────────────────────────────────────────────────
    ("analytics", "Google Analytics",
     lambda h, hd: "google-analytics.com/analytics.js" in h
                   or "gtag/js?id=G-" in h or "gtag/js?id=UA-" in h
                   or "googletagmanager.com/gtag" in h),

    ("analytics", "Google Tag Manager",
     lambda h, hd: "googletagmanager.com/gtm.js" in h or "gtm.js?id=GTM-" in h),

    ("analytics", "Plausible",
     lambda h, hd: "plausible.io/js" in h),

    ("analytics", "Fathom",
     lambda h, hd: "cdn.usefathom.com" in h),

    ("analytics", "Hotjar",
     lambda h, hd: "static.hotjar.com" in h),

    ("analytics", "Mixpanel",
     lambda h, hd: "cdn.mxpnl.com" in h or "mixpanel.com/libs" in h),

    # ── CSS Frameworks ─────────────────────────────────────────────────────
    ("css_framework", "Tailwind CSS",
     lambda h, hd: "tailwindcss" in h or "/tailwind" in h
                   or "cdn.tailwindcss.com" in h or "tailwind.min.css" in h),

    ("css_framework", "Bootstrap",
     lambda h, hd: "bootstrap.min.css" in h or "bootstrap.css" in h or "/bootstrap@" in h),

    ("css_framework", "Bulma",
     lambda h, hd: "bulma.min.css" in h or "bulma.io" in h),

    ("css_framework", "Foundation",
     lambda h, hd: "foundation.min.css" in h),

    # ── Backend / Language hints ───────────────────────────────────────────
    ("backend", "PHP",
     lambda h, hd: _h(hd, "x-powered-by").lower().startswith("php")
                   or ".php" in h),

    ("backend", "Python / Django",
     lambda h, hd: _h(hd, "x-powered-by").lower().find("django") != -1
                   or "csrfmiddlewaretoken" in h),

    ("backend", "Python / Flask",
     lambda h, hd: _h(hd, "server").lower().find("werkzeug") != -1),

    ("backend", "Ruby on Rails",
     lambda h, hd: _h(hd, "x-powered-by").lower().find("phusion passenger") != -1
                   or "rails-ujs" in h or "actioncable" in h),

    ("backend", "Node.js / Express",
     lambda h, hd: _h(hd, "x-powered-by").lower().startswith("express")),

    ("backend", "ASP.NET",
     lambda h, hd: _h(hd, "x-powered-by").lower().find("asp.net") != -1
                   or _h(hd, "x-aspnet-version") != ""),
]


def detect_technologies(html: str, headers: dict) -> dict:
    """
    Detect technologies from page HTML and HTTP response headers.

    Args:
        html:    Full HTML source of the page (string).
        headers: HTTP response headers as a flat dict (keys lowercased).

    Returns:
        {
          "detected": {
            "js_framework": ["React", "jQuery"],
            "cms": ["WordPress"],
            "cdn": ["Cloudflare"],
            ...
          },
          "flat": ["React", "jQuery", "WordPress", "Cloudflare"],
          "count": 4,
          "server": "nginx/1.24",          # raw Server header
          "powered_by": "PHP/8.2",         # raw X-Powered-By header
        }
    """
    html_lower = html.lower() if html else ""
    # Normalise header keys to lowercase for consistent lookup
    norm_headers = {k.lower(): v for k, v in (headers or {}).items()}

    detected: dict[str, list[str]] = {}
    for category, name, match_fn in _SIGNATURES:
        try:
            if match_fn(html_lower, norm_headers):
                detected.setdefault(category, [])
                if name not in detected[category]:
                    detected[category].append(name)
        except Exception:  # noqa: BLE001
            pass

    flat = [name for names in detected.values() for name in names]

    return {
        "detected": detected,
        "flat": flat,
        "count": len(flat),
        "server": norm_headers.get("server", ""),
        "powered_by": norm_headers.get("x-powered-by", ""),
    }


def diff_tech_stacks(previous: list[str], current: list[str]) -> dict:
    """
    Compare two flat technology lists and return what was added/removed.

    Returns:
        {"added": [...], "removed": [...], "unchanged": [...]}
    """
    prev_set = set(previous or [])
    curr_set = set(current or [])
    return {
        "added":     sorted(curr_set - prev_set),
        "removed":   sorted(prev_set - curr_set),
        "unchanged": sorted(prev_set & curr_set),
    }
