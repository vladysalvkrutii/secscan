"""Core scanning logic: fetch a URL and grade its HTTP security headers."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

# Each check: header name -> (weight, short advice shown when missing).
# Weights sum to 100 so the raw score is already a percentage.
SECURITY_HEADERS: dict[str, tuple[int, str]] = {
    "strict-transport-security": (25, "Add HSTS to force HTTPS."),
    "content-security-policy": (25, "Add a CSP to limit resource origins."),
    "x-frame-options": (15, "Add X-Frame-Options to prevent clickjacking."),
    "x-content-type-options": (15, "Add 'nosniff' to stop MIME sniffing."),
    "referrer-policy": (10, "Add Referrer-Policy to control referrers."),
    "permissions-policy": (10, "Add Permissions-Policy to gate browser APIs."),
}


@dataclass
class HeaderResult:
    name: str
    present: bool
    value: str | None
    advice: str | None


@dataclass
class ScanResult:
    url: str
    status_code: int
    score: int
    grade: str
    headers: list[HeaderResult] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "status_code": self.status_code,
            "score": self.score,
            "grade": self.grade,
            "headers": [h.__dict__ for h in self.headers],
        }


class ScanError(Exception):
    """Raised when the target cannot be scanned (bad URL, network error)."""


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def validate_url(url: str) -> str:
    """Only allow http(s) URLs with a host. Keeps the scanner from being
    pointed at arbitrary schemes (file://, etc.)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ScanError("URL must start with http:// or https:// and have a host")
    return url


async def scan_url(url: str, timeout: float = 5.0) -> ScanResult:
    """Fetch ``url`` and score the security headers on the response."""
    validate_url(url)
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True
        ) as client:
            resp = await client.get(url, headers={"User-Agent": "SecScan/1.0"})
    except httpx.HTTPError as exc:
        raise ScanError(f"Request failed: {exc}") from exc

    present = {k.lower(): v for k, v in resp.headers.items()}
    results: list[HeaderResult] = []
    score = 0
    for header, (weight, advice) in SECURITY_HEADERS.items():
        value = present.get(header)
        if value is not None:
            score += weight
            results.append(HeaderResult(header, True, value, None))
        else:
            results.append(HeaderResult(header, False, None, advice))

    return ScanResult(
        url=url,
        status_code=resp.status_code,
        score=score,
        grade=_grade(score),
        headers=results,
    )
