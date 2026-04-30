"""
services/security_service.py
-----------------------------
Basic website security audit:
  - HTTP security header presence check
  - Malware / suspicious code signature scan
  - Security score (0–100)

Runs inside the SEO check flow (no extra HTTP request needed —
headers come from the main page fetch, HTML is already in memory).
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── Security headers ───────────────────────────────────────────────────────
# Each header is worth 20 points → max 100

SECURITY_HEADERS: list[tuple[str, str]] = [
    ("strict-transport-security",  "Strict-Transport-Security (HSTS)"),
    ("x-frame-options",            "X-Frame-Options"),
    ("x-content-type-options",     "X-Content-Type-Options"),
    ("x-xss-protection",           "X-XSS-Protection"),
    ("content-security-policy",    "Content-Security-Policy"),
]

POINTS_PER_HEADER = 20  # 5 headers × 20 = 100

# ── Malware signatures ─────────────────────────────────────────────────────
# Patterns that indicate injected malicious code in HTML source.

_MALWARE_PATTERNS: list[tuple[str, str]] = [
    (r"eval\s*\(\s*base64_decode",          "eval(base64_decode) — obfuscated PHP execution"),
    (r"eval\s*\(\s*unescape",               "eval(unescape) — obfuscated JS execution"),
    (r"document\.write\s*\(\s*unescape",    "document.write(unescape) — obfuscated JS injection"),
    (r"crypto[-_]?miner",                   "Crypto-miner reference"),
    (r"coinhive",                           "CoinHive crypto-miner"),
    (r"cryptonight",                        "CryptoNight miner"),
    (r"malicious[-_]?script",               "Explicit malicious-script marker"),
    (r"<script[^>]*src=['\"]https?://[^'\"]*\.ru/", "External script from .ru domain"),
    (r"fromcharcode",                       "String.fromCharCode obfuscation"),
    (r"\\x[0-9a-f]{2}\\x[0-9a-f]{2}\\x[0-9a-f]{2}", "Hex-encoded obfuscation sequence"),
]

_COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), label)
    for pattern, label in _MALWARE_PATTERNS
]


# ── Public API ─────────────────────────────────────────────────────────────

def run_security_audit(html: str, response_headers: dict) -> dict:
    """
    Run a full security audit on a fetched page.

    Args:
        html:             Full HTML source of the page.
        response_headers: HTTP response headers (keys lowercased).

    Returns:
        {
          "score":    int (0–100),
          "headers":  {"strict-transport-security": True, ...},
          "issues":   ["Missing X-Frame-Options", ...],
          "malware":  ["eval(base64_decode) — ...", ...],
        }
    """
    header_results, header_issues = _check_security_headers(response_headers)
    malware_flags = _scan_for_malware(html)

    # Score: header points only (malware doesn't reduce score — it's a separate flag)
    present_count = sum(1 for v in header_results.values() if v)
    score = present_count * POINTS_PER_HEADER

    issues = list(header_issues)
    if malware_flags:
        issues.append(f"{len(malware_flags)} malware signature(s) detected")

    logger.debug(
        "[SECURITY] score=%d headers_present=%d malware=%d",
        score, present_count, len(malware_flags),
    )

    return {
        "score":   score,
        "headers": header_results,
        "issues":  issues,
        "malware": malware_flags,
    }


# ── Private helpers ────────────────────────────────────────────────────────

def _check_security_headers(headers: dict) -> tuple[dict, list[str]]:
    """
    Check presence of each security header.
    Returns (results_dict, list_of_missing_header_labels).
    """
    norm = {k.lower(): v for k, v in (headers or {}).items()}
    results: dict[str, bool] = {}
    issues: list[str] = []

    for header_key, label in SECURITY_HEADERS:
        present = header_key in norm and bool(norm[header_key])
        results[header_key] = present
        if not present:
            issues.append(f"Missing {label}")

    return results, issues


def _scan_for_malware(html: str) -> list[str]:
    """
    Scan HTML source for known malware/obfuscation signatures.
    Returns list of matched labels (empty = clean).
    """
    if not html:
        return []

    found: list[str] = []
    for pattern, label in _COMPILED_PATTERNS:
        if pattern.search(html):
            found.append(label)

    return found
