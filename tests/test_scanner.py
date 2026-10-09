"""Unit tests for the scanner scoring logic."""

import pytest

from app.scanner import ScanError, _grade, validate_url


def test_grade_boundaries():
    assert _grade(100) == "A"
    assert _grade(90) == "A"
    assert _grade(80) == "B"
    assert _grade(60) == "C"
    assert _grade(45) == "D"
    assert _grade(0) == "F"


def test_validate_url_accepts_http_and_https():
    assert validate_url("https://example.com") == "https://example.com"
    assert validate_url("http://example.com/path") == "http://example.com/path"


@pytest.mark.parametrize("bad", ["file:///etc/passwd", "ftp://x", "notaurl", ""])
def test_validate_url_rejects_non_http(bad):
    with pytest.raises(ScanError):
        validate_url(bad)
