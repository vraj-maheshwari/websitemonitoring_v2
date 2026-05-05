"""
services/security_service.py
-----------------------------
Comprehensive security audit module with 5 check categories:

  A. HTTP Security Headers (30 pts)
  B. Content Security Policy Analysis (20 pts)
  C. CORS Misconfiguration (15 pts)
  D. Mixed Content & HTTPS Quality (15 pts)
  E. Malware & Injection Signals (20 pts)

Total: 0–100 weighted score with letter grades (A/B/C/D/F)

Runs inside the SEO check flow (no extra HTTP request needed —
headers come from the main page fetch, HTML is already in memory).
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY A: HTTP Security Headers (30 pts)
# ══════════════════════════════════════════════════════════════════════════════

# Header definitions with point values
_HTTP_HEADERS = [
    ("strict-transport-security", "Strict-Transport-Security (HSTS)", 8),
    ("x-frame-options", "X-Frame-Options", 5),
    ("x-content-type-options", "X-Content-Type-Options", 5),
    ("x-xss-protection", "X-XSS-Protection", 2),
    ("referrer-policy", "Referrer-Policy", 5),
    ("permissions-policy", "Permissions-Policy", 5),
]

# Valid values for headers
_VALID_XFO_VALUES = {"deny", "sameorigin"}
_VALID_REFERRER_POLICY = {
    "no-referrer",
    "no-referrer-when-downgrade",
    "origin",
    "origin-when-cross-origin",
    "same-origin",
    "strict-origin",
    "strict-origin-when-cross-origin",
    "unsafe-url",
}


def _check_http_security_headers(headers: dict) -> dict:
    """
    Check HTTP security headers with granular scoring.
    Returns dict with score, max_score, issues, and details.
    """
    norm = {k.lower(): v for k, v in (headers or {}).items()}
    details: dict = {}
    issues: list[str] = []
    score = 0
    max_score = 0

    for header_key, label, base_points in _HTTP_HEADERS:
        max_score += base_points
        header_value = norm.get(header_key, "")
        present = bool(header_value)

        header_detail = {
            "present": present,
            "value": header_value if present else None,
            "score": 0,
        }

        if present:
            # Base points for presence
            header_detail["score"] = base_points
            score += base_points

            # Bonus points for HSTS
            if header_key == "strict-transport-security":
                # +2 if max-age >= 31536000 (1 year)
                if "max-age=" in header_value.lower():
                    try:
                        # Extract max-age value
                        parts = header_value.lower().split("max-age=")
                        if len(parts) > 1:
                            max_age_str = parts[1].split()[0].split(";")[0]
                            max_age = int(max_age_str)
                            if max_age >= 31536000:
                                header_detail["score"] += 2
                                score += 2
                                max_score += 2
                                header_detail["hsts_long_duration"] = True
                    except (ValueError, IndexError):
                        pass

                # +1 if includeSubDomains
                if "includesubdomains" in header_value.lower():
                    header_detail["score"] += 1
                    score += 1
                    max_score += 1
                    header_detail["hsts_include_subdomains"] = True

            # Validate X-Frame-Options value
            elif header_key == "x-frame-options":
                xfo_value = header_value.strip().lower()
                if xfo_value == "deny":
                    header_detail["score"] += 0  # Already have base points
                    header_detail["xfo_level"] = "deny"
                elif xfo_value == "sameorigin":
                    header_detail["score"] += 0
                    header_detail["xfo_level"] = "sameorigin"
                else:
                    issues.append(f"X-Frame-Options has unknown value: {header_value}")

            # Validate Referrer-Policy
            elif header_key == "referrer-policy":
                rp_value = header_value.strip().lower().split(",")[0]
                if rp_value in _VALID_REFERRER_POLICY:
                    header_detail["referrer_policy"] = rp_value
                else:
                    issues.append(f"Unknown Referrer-Policy value: {header_value}")

        else:
            issues.append(f"Missing {label}")

        details[header_key] = header_detail

    return {
        "score": min(score, max_score),
        "max_score": max_score,
        "issues": issues,
        "details": details,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY B: Content Security Policy Analysis (20 pts)
# ══════════════════════════════════════════════════════════════════════════════

def _parse_csp(csp_string: str) -> dict:
    """Parse CSP header value into directive dict."""
    directives: dict = {}
    if not csp_string:
        return directives

    for directive in csp_string.split(";"):
        directive = directive.strip()
        if not directive:
            continue
        parts = directive.split()
        if parts:
            directive_name = parts[0].lower()
            directive_values = parts[1:] if len(parts) > 1 else []
            directives[directive_name] = directive_values

    return directives


def _check_csp(headers: dict) -> dict:
    """
    Analyze Content Security Policy quality.
    """
    norm = {k.lower(): v for k, v in (headers or {}).items()}
    csp_header = norm.get("content-security-policy", "")
    issues: list[str] = []
    score = 0
    max_score = 20

    details: dict = {
        "present": bool(csp_header),
        "directives": {},
        "script_src": [],
        "unsafe_inline": False,
        "unsafe_eval": False,
        "wildcard_source": False,
    }

    if not csp_header:
        issues.append("No Content-Security-Policy header found")
        return {
            "score": 0,
            "max_score": max_score,
            "issues": issues,
            "details": details,
        }

    # Base 8 points for CSP presence
    score += 8
    details["directives"] = _parse_csp(csp_header)

    # Get script-src directive - flatten the list for checking
    script_src_raw = details["directives"].get("script-src", [])
    # Join and check for unsafe patterns
    script_src_str = " ".join(script_src_raw).lower()
    details["script_src"] = script_src_raw

    # Check for unsafe-inline (various forms)
    unsafe_inline_patterns = ["unsafe-inline", "'unsafe-inline'"]
    if any(pattern in script_src_str for pattern in unsafe_inline_patterns):
        details["unsafe_inline"] = True
        issues.append("CSP allows unsafe-inline scripts — XSS risk")
    else:
        score += 4

    # Check for unsafe-eval
    unsafe_eval_patterns = ["unsafe-eval", "'unsafe-eval'"]
    if any(pattern in script_src_str for pattern in unsafe_eval_patterns):
        details["unsafe_eval"] = True
        issues.append("CSP allows eval() — code injection risk")
    else:
        score += 4

    # Check for wildcard in script-src
    if "*" in script_src_raw or "*" in script_src_str:
        details["wildcard_source"] = True
        issues.append("CSP uses wildcard source in script-src — defeats purpose of CSP")
    else:
        score += 4

    return {
        "score": min(score, max_score),
        "max_score": max_score,
        "issues": issues,
        "details": details,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY C: CORS Misconfiguration (15 pts)
# ══════════════════════════════════════════════════════════════════════════════

def _check_cors(headers: dict, url: str) -> dict:
    """
    Check CORS configuration from response headers.
    No preflight needed — uses main page response headers.
    """
    norm = {k.lower(): v for k, v in (headers or {}).items()}
    issues: list[str] = []
    score = 0
    max_score = 15

    acao = norm.get("access-control-allow-origin", "")
    acac = norm.get("access-control-allow-credentials", "")
    acam = norm.get("access-control-allow-methods", "")

    details: dict = {
        "acao_present": bool(acao),
        "acao_value": acao,
        "acac_value": acac,
        "acam_value": acam,
    }

    if not acao:
        # No CORS header = safe (not exposing CORS)
        score = 15
        details["classification"] = "not_exposed"
    elif acao == "*":
        # Wildcard origin
        if acac and acac.lower() == "true":
            # Critical: wildcard with credentials
            issues.append("CRITICAL: CORS allows any origin with credentials — auth bypass risk")
            score = 0
            details["classification"] = "critical_misconfig"
        elif acam and ("delete" in acam.lower() or "put" in acam.lower()):
            issues.append("CORS exposes DELETE/PUT to any origin")
            score = 8
            details["classification"] = "wildcard_public"
        else:
            # Wildcard but no credentials = acceptable for public API
            score = 8
            details["classification"] = "wildcard_no_credentials"
    elif acao.lower() == "null":
        issues.append("CORS allows null origin — sandbox bypass possible")
        score = 3
        details["classification"] = "null_origin"
    else:
        # Specific origin (good)
        score = 15
        details["classification"] = "specific_origin"
        details["allowed_origin"] = acao

    # Check for dangerous methods
    if acam and acao == "*":
        dangerous_methods = [m for m in ["delete", "put", "patch"] if m in acam.lower()]
        if dangerous_methods:
            issues.append(f"CORS exposes dangerous methods: {', '.join(dangerous_methods)}")

    return {
        "score": min(score, max_score),
        "max_score": max_score,
        "issues": issues,
        "details": details,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY D: Mixed Content & HTTPS Quality (15 pts)
# ══════════════════════════════════════════════════════════════════════════════

def _check_mixed_content(html: str, headers: dict) -> dict:
    """
    Scan HTML for HTTP resources embedded in HTTPS page.
    """
    issues: list[str] = []
    score = 0
    max_score = 15

    # Count mixed content by type
    counts = {
        "http_scripts": 0,
        "http_images": 0,
        "http_iframes": 0,
        "http_stylesheets": 0,
        "http_fonts": 0,
        "http_other": 0,
    }

    if not html:
        return {
            "score": max_score,
            "max_score": max_score,
            "issues": [],
            "details": {"total_mixed": 0, **counts},
        }

    html_lower = html.lower()

    # Check <script src="http://...">
    script_matches = re.findall(r'<script[^>]+src=["\']http://([^"\']+)', html, re.IGNORECASE)
    counts["http_scripts"] = len(script_matches)

    # Check <link href="http://..."> (stylesheets)
    link_matches = re.findall(r'<link[^>]+href=["\']http://([^"\']+)', html, re.IGNORECASE)
    counts["http_stylesheets"] = len(link_matches)

    # Check <img src="http://...">
    img_matches = re.findall(r'<img[^>]+src=["\']http://([^"\']+)', html, re.IGNORECASE)
    counts["http_images"] = len(img_matches)

    # Check <iframe src="http://...">
    iframe_matches = re.findall(r'<iframe[^>]+src=["\']http://([^"\']+)', html, re.IGNORECASE)
    counts["http_iframes"] = len(iframe_matches)

    # Check inline styles with url(http://...)
    style_url_matches = re.findall(r'url\s*\(\s*["\']?http://', html, re.IGNORECASE)
    counts["http_fonts"] = len(style_url_matches)

    total_mixed = sum(counts.values())

    # Scoring
    if total_mixed == 0:
        score = 8  # All resources use HTTPS
    else:
        # Deduct points based on mixed content count
        if counts["http_scripts"] > 0:
            issues.append(f"{counts['http_scripts']} script(s) load over HTTP — mixed content warning")
        if counts["http_images"] > 0:
            issues.append(f"{counts['http_images']} image(s) load over HTTP — mixed content warning in browsers")
        if counts["http_iframes"] > 0:
            issues.append(f"{counts['http_iframes']} iframe(s) load over HTTP — security risk")
        if counts["http_stylesheets"] > 0:
            issues.append(f"{counts['http_stylesheets']} stylesheet(s) load over HTTP — blocks HTTPS indicator")
        if counts["http_fonts"] > 0:
            issues.append(f"{counts['http_fonts']} font resource(s) load over HTTP — mixed content")

        # Score based on severity
        if counts["http_scripts"] > 0:
            score = max(0, 8 - (total_mixed * 1))
        else:
            score = max(0, 8 - (total_mixed * 0.5))

    # Check HTTPS redirect (from headers)
    norm = {k.lower(): v for k, v in (headers or {}).items()}
    # If the original URL was HTTP and we got redirected to HTTPS, that's good
    # This is handled separately in the main scoring

    return {
        "score": min(score, max_score),
        "max_score": max_score,
        "issues": issues,
        "details": {"total_mixed": total_mixed, **counts},
    }


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY E: Malware & Injection Signals (20 pts)
# ══════════════════════════════════════════════════════════════════════════════

# Malware patterns with severity and deductions
_MALWARE_PATTERNS = [
    # Existing patterns (keep)
    (r"eval\s*\(\s*base64_decode", "high", 5, "eval(base64_decode) — obfuscated PHP execution"),
    (r"eval\s*\(\s*unescape", "high", 5, "eval(unescape) — obfuscated JS execution"),
    (r"document\.write\s*\(\s*unescape", "medium", 4, "document.write(unescape) — obfuscated JS injection"),
    (r"coinhive", "high", 8, "CoinHive crypto-miner"),
    (r"cryptonight", "high", 8, "CryptoNight miner"),
    (r"crypto[-_]?miner", "high", 8, "Crypto-miner reference"),
    (r"fromcharcode", "low", 3, "String.fromCharCode obfuscation"),
    (r"malicious[-_]?script", "high", 6, "Explicit malicious-script marker"),
    (r"<script[^>]*src=['\"]https?://[^'\"]*\.ru/", "high", 6, "External script from .ru domain"),
    (r"\\x[0-9a-f]{2}\\x[0-9a-f]{2}\\x[0-9a-f]{2}", "low", 3, "Hex-encoded obfuscation sequence"),

    # New patterns
    (r"<script[^>]*>document\.location\s*=", "high", 6, "Script redirecting document.location — possible hijacking"),
    (r"window\.location\.replace\s*\(", "medium", 3, "window.location.replace() — potential open redirect"),
    (r"\batob\s*\(", "medium", 3, "atob() — base64 decode in JavaScript"),
    (r"fromcharcode.*eval", "high", 6, "fromCharCode combined with eval — obfuscation attack"),
    (r"\.ru\/[a-z0-9]{8,}\.js", "high", 6, "Random-looking .ru JS path — suspicious external script"),
    (r"\.xyz\/[a-z0-9]{8,}\.js", "high", 5, "Random-looking .xyz JS path — suspicious external script"),
    (r"<iframe[^>]*style\s*=\s*[\"'].*display\s*:\s*none", "high", 6, "Hidden iframe injection"),
    (r"<link[^>]+rel\s*=[^>]*http://", "medium", 3, "External resource injection via link tag"),
    (r"unescape\s*\(\s*%u", "high", 5, "Unicode unescape obfuscation"),
    (r"javascript\s*:\s*void\s*\([^)]*\)", "low", 2, "javascript:void() in href — potential phishing"),
]

_COMPILED_MALWARE_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), severity, deduction, description)
    for pattern, severity, deduction, description in _MALWARE_PATTERNS
]


def _scan_for_malware(html: str) -> dict:
    """
    Scan HTML for malware/obfuscation signatures.
    Returns dict with score, issues, and malware_flags.
    """
    issues: list[str] = []
    malware_flags: list[dict] = []
    score = 20  # Start with full points
    max_score = 20

    if not html:
        return {
            "score": max_score,
            "max_score": max_score,
            "issues": [],
            "malware_flags": [],
        }

    found_high = False

    for pattern, severity, deduction, description in _COMPILED_MALWARE_PATTERNS:
        if pattern.search(html):
            flag = {
                "pattern": description.split(" — ")[0],
                "severity": severity,
                "description": description,
                "deduction": deduction,
            }
            malware_flags.append(flag)
            issues.append(description)

            # Deduct from score
            score -= deduction

            if severity == "high":
                found_high = True

    # Score floor: 0 minimum
    score = max(0, score)

    # If any HIGH severity found, minimum is 0
    if found_high:
        score = 0

    return {
        "score": score,
        "max_score": max_score,
        "issues": issues,
        "malware_flags": malware_flags,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def run_security_audit(html: str, response_headers: dict, url: str = "") -> dict:
    """
    Run a comprehensive security audit on a fetched page.

    Args:
        html:              Full HTML source of the page.
        response_headers:  HTTP response headers (keys lowercased).
        url:               The original URL (needed for CORS checks).

    Returns:
        {
          "score": int,           # 0–100 weighted total
          "grade": str,            # "A" ≥80, "B" ≥65, "C" ≥50, "D" ≥35, "F" <35

          "categories": {
            "headers":       { "score": int, "max": 30, "issues": [], "details": {} },
            "csp":           { "score": int, "max": 20, "issues": [], "details": {} },
            "cors":          { "score": int, "max": 15, "issues": [], "details": {} },
            "mixed_content": { "score": int, "max": 15, "issues": [], "details": {} },
            "malware":       { "score": int, "max": 20, "issues": [], "malware_flags": [] },
          },

          # Flat lists for backward compatibility
          "security_headers": { "strict-transport-security": bool, ... },
          "security_issues":  [ "all issues from all categories merged" ],
          "malware_flags":    [ "pattern description strings" ],
        }
    """
    # Run each category
    headers_result = _check_http_security_headers(response_headers)
    csp_result = _check_csp(response_headers)
    cors_result = _check_cors(response_headers, url)
    mixed_result = _check_mixed_content(html, response_headers)
    malware_result = _scan_for_malware(html)

    # Calculate total score
    total_score = (
        headers_result["score"]
        + csp_result["score"]
        + cors_result["score"]
        + mixed_result["score"]
        + malware_result["score"]
    )

    # Calculate max possible
    max_total = (
        headers_result["max_score"]
        + csp_result["max_score"]
        + cors_result["max_score"]
        + mixed_result["max_score"]
        + malware_result["max_score"]
    )

    # Normalize to 0-100
    if max_total > 0:
        normalized_score = int((total_score / max_total) * 100)
    else:
        normalized_score = 0

    # Calculate grade
    if normalized_score >= 80:
        grade = "A"
    elif normalized_score >= 65:
        grade = "B"
    elif normalized_score >= 50:
        grade = "C"
    elif normalized_score >= 35:
        grade = "D"
    else:
        grade = "F"

    # Merge all issues
    all_issues = (
        headers_result["issues"]
        + csp_result["issues"]
        + cors_result["issues"]
        + mixed_result["issues"]
        + malware_result["issues"]
    )

    # Build backward-compatible security_headers dict
    backward_headers = {}
    for header_key, _, _ in _HTTP_HEADERS:
        backward_headers[header_key] = headers_result["details"].get(header_key, {}).get("present", False)

    # Build backward-compatible malware flags list
    backward_malware = [f["description"] for f in malware_result["malware_flags"]]

    # Build categories dict
    categories = {
        "headers": {
            "score": headers_result["score"],
            "max": headers_result["max_score"],
            "issues": headers_result["issues"],
            "details": headers_result["details"],
        },
        "csp": {
            "score": csp_result["score"],
            "max": csp_result["max_score"],
            "issues": csp_result["issues"],
            "details": csp_result["details"],
        },
        "cors": {
            "score": cors_result["score"],
            "max": cors_result["max_score"],
            "issues": cors_result["issues"],
            "details": cors_result["details"],
        },
        "mixed_content": {
            "score": mixed_result["score"],
            "max": mixed_result["max_score"],
            "issues": mixed_result["issues"],
            "details": mixed_result["details"],
        },
        "malware": {
            "score": malware_result["score"],
            "max": malware_result["max_score"],
            "issues": malware_result["issues"],
            "malware_flags": malware_result["malware_flags"],
        },
    }

    logger.debug(
        "[SECURITY] score=%d grade=%s headers=%d csp=%d cors=%d mixed=%d malware=%d",
        normalized_score, grade,
        headers_result["score"], csp_result["score"], cors_result["score"],
        mixed_result["score"], malware_result["score"],
    )

    return {
        "score": normalized_score,
        "grade": grade,
        "categories": categories,
        # Backward compatibility
        "security_headers": backward_headers,
        "security_issues": all_issues,
        "malware_flags": backward_malware,
    }


def run_security_check(site_id: int) -> dict:
    """
    Run a security check for a site. Fetches the page and runs security audit.
    Updates the site model with results.
    """
    from app import create_app
    from app.models.site import Site
    from app.services.monitor_service import fetch_page
    from app.utils.time import now_utc

    app = create_app()
    with app.app_context():
        site = db.session.get(Site, site_id)
        if not site:
            return {"error": "Site not found"}

        try:
            # Fetch the page
            fetch_result = fetch_page(site.url)
            if not fetch_result["success"]:
                site.security_status = "failed"
                site.security_last_error = fetch_result.get("error", "Fetch failed")
                site.refresh_app_status()
                return {"error": fetch_result.get("error", "Fetch failed")}

            html = fetch_result["html"]
            headers = fetch_result["headers"]

            # Run security audit
            audit_result = run_security_audit(html, headers, site.url)

            # Update site
            site.security_score = audit_result["score"]
            site.security_grade = audit_result["grade"]
            site.security_status = "done"
            site.last_security_check_at = now_utc()
            site.next_security_check_at = now_utc() + timedelta(seconds=site.security_check_interval)
            site.security_last_error = None
            site.refresh_app_status()

            # Log the result
            logger.info(
                "[SECURITY CHECK] site_id=%s score=%d grade=%s",
                site_id, audit_result["score"], audit_result["grade"]
            )

            return audit_result

        except Exception as e:
            logger.error("[SECURITY CHECK] site_id=%s error: %s", site_id, str(e))
            site.security_status = "failed"
            site.security_last_error = str(e)
            site.refresh_app_status()
            return {"error": str(e)}
