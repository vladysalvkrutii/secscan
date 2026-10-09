"""SecScan API — FastAPI application entrypoint.

Endpoints:
  GET /health   liveness/readiness probe
  GET /scan     scan a URL's security headers  (?url=https://example.com)
  GET /metrics  Prometheus exposition format
"""

from __future__ import annotations

import json
import logging
import sys
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from . import __version__
from .metrics import SCAN_DURATION, SCAN_ERRORS_TOTAL, SCANS_TOTAL
from .scanner import ScanError, scan_url


# ── Structured JSON logging (one JSON object per line; Loki/ELK friendly) ──
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.__dict__.get("extra_fields"):
            payload.update(record.__dict__["extra_fields"])
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    return logging.getLogger("secscan")


log = _configure_logging()

app = FastAPI(
    title="SecScan API",
    description="Scan a URL's HTTP security headers and grade them A–F.",
    version=__version__,
)

# Prometheus scrape endpoint.
app.mount("/metrics", make_asgi_app())


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/scan")
async def scan(
    url: str = Query(..., description="Target URL, e.g. https://example.com"),
) -> JSONResponse:
    start = time.perf_counter()
    try:
        result = await scan_url(url)
    except ScanError as exc:
        SCAN_ERRORS_TOTAL.inc()
        log.warning(
            "scan failed",
            extra={"extra_fields": {"url": url, "error": str(exc)}},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    elapsed = time.perf_counter() - start
    SCAN_DURATION.observe(elapsed)
    SCANS_TOTAL.labels(grade=result.grade).inc()
    log.info(
        "scan completed",
        extra={
            "extra_fields": {
                "url": url,
                "grade": result.grade,
                "score": result.score,
                "duration_s": round(elapsed, 3),
            }
        },
    )
    return JSONResponse(result.as_dict())
