"""API-level tests (no network: scanning real URLs is covered manually)."""

from fastapi.testclient import TestClient

from app.main import app
from app.scanner import SECURITY_HEADERS

client = TestClient(app)


def test_header_weights_sum_to_100():
    assert sum(weight for weight, _ in SECURITY_HEADERS.values()) == 100


def test_root():
    body = client.get("/").json()
    assert body["name"] == "SecScan"
    assert "version" in body


def test_health():
    body = client.get("/health").json()
    assert body["status"] == "ok"


def test_scan_rejects_non_http():
    resp = client.get("/scan", params={"url": "file:///etc/passwd"})
    assert resp.status_code == 400


def test_metrics_endpoint_exposes_counters():
    # /metrics is mounted, so it answers on the trailing-slash path.
    text = client.get("/metrics/").text
    assert "secscan_scans_total" in text
