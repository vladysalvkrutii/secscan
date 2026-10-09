"""SecScan API — FastAPI application entrypoint.

Endpoints:
  GET /          service metadata
  GET /health    liveness/readiness probe
  GET /scan      scan a URL's security headers  (?url=https://example.com)
  GET /metrics   Prometheus exposition format
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from prometheus_client import make_asgi_app
from pydantic import BaseModel, Field

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


# ── API response models (power the auto-generated OpenAPI docs) ────────────
class ServiceInfo(BaseModel):
    name: str = "SecScan"
    version: str
    description: str
    docs: str = "/docs"
    example: str = "/scan?url=https://github.com"


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


class HeaderCheck(BaseModel):
    name: str
    present: bool
    value: str | None = None
    advice: str | None = None


class ScanResponse(BaseModel):
    url: str
    status_code: int
    score: int = Field(..., ge=0, le=100)
    grade: str = Field(..., examples=["A"])
    headers: list[HeaderCheck]


app = FastAPI(
    title="SecScan API",
    description=(
        "Scan a URL's HTTP security headers (HSTS, CSP, X-Frame-Options, …) "
        "and grade them **A–F**."
    ),
    version=__version__,
    license_info={"name": "MIT"},
    contact={"name": "Vladyslav Krutii", "url": "https://github.com/vladysalvkrutii"},
)

# Prometheus scrape endpoint.
app.mount("/metrics", make_asgi_app())


_STATIC = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
async def ui() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


@app.get("/info", response_model=ServiceInfo, tags=["meta"])
async def info() -> ServiceInfo:
    return ServiceInfo(
        version=__version__,
        description="Security headers scanner API.",
    )


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@app.get("/scan", response_model=ScanResponse, tags=["scan"])
async def scan(
    url: str = Query(
        ...,
        description="Target URL to scan.",
        examples=["https://github.com"],
    ),
) -> ScanResponse:
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
    return ScanResponse(**result.as_dict())
