# Issue #4 — Metrics Dashboard: Implementation Guide

> **Current state of the codebase at the time of writing this guide:**
> - ✅ `middleware/rate_limiter.py` — Clean. Has ban check, sliding window, post-response risk scoring.
> - ✅ `services/risk_engine.py` — Lua-based atomic decay, multi-dimensional scoring.
> - ✅ `.env` — All reputation engine and signal weight variables are set.
> - ⚠️ `config.py` — Has **duplicate field definitions** (lines 24–66). Fix this first.
> - 📁 `app/metrics/` — Folder exists but is empty.
> - ❌ `docker-compose.yml`, `Dockerfile` — Do not exist yet.

---

## Step 0 — Fix `config.py` (do this first)

Your `config.py` has `COOLDOWN_DURATION_SECONDS`, `RISK_DECAY_RATE`, thresholds, and signal weights declared **three times**. This will cause a Pydantic `DuplicateField` error. Replace the entire file contents with this clean version:

```python
from pydantic_settings import BaseSettings
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    DATABASE_URL: str

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    BAN_DURATION_SECONDS: int

    RATE_LIMIT_REQUESTS: int
    RATE_LIMIT_WINDOW_SECONDS: int

    TOKEN_BUCKET_CAPACITY: int
    TOKEN_BUCKET_REFILL_RATE: float

    COOLDOWN_DURATION_SECONDS: int

    # Reputation Engine
    RISK_DECAY_RATE: float = 0.95

    # Risk Thresholds
    RISK_THROTTLE_THRESHOLD: int
    RISK_LIGHT_THROTTLE_THRESHOLD: int
    RISK_HEAVY_THROTTLE_THRESHOLD: int
    RISK_BAN_THRESHOLD: int

    # Signal Weights
    WEIGHT_RATE_LIMIT_SLIDING: float
    WEIGHT_RATE_LIMIT_TOKEN: float
    WEIGHT_BURST_DETECTED: float
    WEIGHT_INVALID_API_KEY: float
    WEIGHT_STATUS_401: float
    WEIGHT_STATUS_403: float
    WEIGHT_STATUS_404: float

    class Config:
        env_file = str(ENV_FILE)

settings = Settings()
```

**Verify:**
```bash
python -c "from app.config import settings; print('OK:', settings.RISK_BAN_THRESHOLD)"
# Expected: OK: 80
```

---

## Step 1 — Install `prometheus-client`

```bash
pip install prometheus-client==0.20.0
```

Add to `requirements.txt`:
```
prometheus-client==0.20.0
```

---

## Step 2 — Create the Metrics Registry

Your `app/metrics/` folder already exists and is empty. Create two files inside it.

### `app/metrics/__init__.py`
Leave completely empty.

### `app/metrics/registry.py`

```python
from prometheus_client import Counter, Histogram, Gauge


REQUESTS_TOTAL = Counter(
    "aegis_requests_total",
    "Total HTTP requests processed by Aegis gateway",
    ["method", "path_group", "status_code", "block_reason"],
)

BLOCKED_REQUESTS_TOTAL = Counter(
    "aegis_blocked_requests_total",
    "Requests blocked by each protection layer",
    ["algorithm"],
)

BURST_DETECTIONS_TOTAL = Counter(
    "aegis_burst_detections_total",
    "Number of burst attack events detected",
)

BANS_TRIGGERED_TOTAL = Counter(
    "aegis_bans_triggered_total",
    "Number of times an IP or API key was banned",
)

COOLDOWNS_SET_TOTAL = Counter(
    "aegis_cooldowns_set_total",
    "Number of cooldowns applied to IPs",
)

REQUEST_DURATION_SECONDS = Histogram(
    "aegis_request_duration_seconds",
    "HTTP request duration from middleware entry to response",
    ["method", "path_group"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

RISK_SCORE_HISTOGRAM = Histogram(
    "aegis_risk_score_distribution",
    "Distribution of IP/key risk scores at request time",
    buckets=[0, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
)

TOKEN_BUCKET_REMAINING = Gauge(
    "aegis_token_bucket_remaining_tokens",
    "Token bucket remaining tokens for the most recently evaluated request",
)


def get_path_group(path: str) -> str:
    """Normalise raw URL path into a bounded label value."""
    if path.startswith("/auth"):
        return "/auth/*"
    if path.startswith("/api/keys") or path.startswith("/api-keys"):
        return "/api/keys/*"
    if path.startswith("/analytics"):
        return "/analytics/*"
    if path == "/":
        return "/"
    return "/other"
```

**Why bounded path groups?**
Each unique label combination = one time series in Prometheus memory. Using raw paths like `/api/keys/1`, `/api/keys/2`... creates thousands of time series → OOM crash. Five groups keep it safe.

**Verify:**
```bash
python -c "
from app.metrics.registry import get_path_group, REQUESTS_TOTAL
print(get_path_group('/auth/login'))   # /auth/*
print(get_path_group('/api/keys/5'))  # /api/keys/*
print(get_path_group('/unknown'))     # /other
print('Registry OK')
"
```

---

## Step 3 — Instrument `app/middleware/rate_limiter.py`

Make **4 targeted edits** to the existing file. Do not rewrite it.

### Edit 1 — New imports (add after line 16)

After `from app.services.audit_service import create_log`, add:

```python
import time as time_module

from app.services.risk_engine import get_decayed_score
from app.metrics.registry import (
    REQUESTS_TOTAL,
    BLOCKED_REQUESTS_TOTAL,
    BURST_DETECTIONS_TOTAL,
    BANS_TRIGGERED_TOTAL,
    COOLDOWNS_SET_TOTAL,
    REQUEST_DURATION_SECONDS,
    RISK_SCORE_HISTOGRAM,
    TOKEN_BUCKET_REMAINING,
    get_path_group,
)
```

### Edit 2 — Timer variables (inside `dispatch`, right after `ip = request.client.host`)

```python
ip = request.client.host
api_key_id = request.headers.get("X-API-Key", "") or ""
# ↓ Add these four lines
method = request.method
path_group = get_path_group(request.url.path)
start_time = time_module.time()
tokens_remaining = 0
```

### Edit 3 — Metric calls at each blocking `return`

**At IP ban check**, before the `return JSONResponse(status_code=403 ...)`:
```python
if is_banned(ip):
    BLOCKED_REQUESTS_TOTAL.labels(algorithm="ban").inc()
    REQUESTS_TOTAL.labels(method=method, path_group=path_group,
        status_code="403", block_reason="ip_banned").inc()
    REQUEST_DURATION_SECONDS.labels(method=method, path_group=path_group).observe(
        time_module.time() - start_time)
    return JSONResponse(status_code=403, content={"detail": "IP temporarily banned"})
```

**At API key ban check**, before the `return JSONResponse(status_code=403 ...)`:
```python
if api_key_id and is_key_banned(api_key_id):
    BLOCKED_REQUESTS_TOTAL.labels(algorithm="ban").inc()
    REQUESTS_TOTAL.labels(method=method, path_group=path_group,
        status_code="403", block_reason="key_banned").inc()
    REQUEST_DURATION_SECONDS.labels(method=method, path_group=path_group).observe(
        time_module.time() - start_time)
    return JSONResponse(status_code=403, content={"detail": "API key temporarily banned"})
```

**At rate limit exceeded block** (`if not allowed:`), before the final `return`:
```python
    risk_status = evaluate_risk(ip=ip, api_key_id=api_key_id or None)

    if risk_status == "banned":
        BANS_TRIGGERED_TOTAL.inc()

    BLOCKED_REQUESTS_TOTAL.labels(algorithm="sliding_window").inc()
    REQUESTS_TOTAL.labels(method=method, path_group=path_group,
        status_code="429", block_reason="sliding_window").inc()
    REQUEST_DURATION_SECONDS.labels(method=method, path_group=path_group).observe(
        time_module.time() - start_time)

    return JSONResponse(status_code=429, content={...})
```

### Edit 4 — Record metrics for successful requests (before `return response`)

Insert this block between the final `except Exception: pass` and `return response`:

```python
    except Exception:
        pass  # Redis down → skip scoring, don't crash

    # ── Metrics for allowed requests ─────────────────────────
    try:
        ip_score = get_decayed_score(f"ip:{ip}")
        key_score = get_decayed_score(f"key:{api_key_id}") if api_key_id else 0.0
        max_risk_score = max(ip_score, key_score)

        RISK_SCORE_HISTOGRAM.observe(max_risk_score)
        TOKEN_BUCKET_REMAINING.set(tokens_remaining)
        REQUEST_DURATION_SECONDS.labels(method=method, path_group=path_group).observe(
            time_module.time() - start_time)
        REQUESTS_TOTAL.labels(
            method=method, path_group=path_group,
            status_code=str(response.status_code), block_reason="none"
        ).inc()

        response.headers["X-RateLimit-Risk-Score"] = str(int(max_risk_score))
    except Exception:
        pass

    return response
```

**Verify:**
```bash
uvicorn app.main:app --reload
curl http://localhost:8000/
curl http://localhost:8000/
# Server should behave identically — metrics recording doesn't change behaviour
```

---

## Step 4 — Add `/metrics` to `app/main.py`

### New imports (add after `from fastapi import FastAPI`)

```python
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
```

### New route (add after the existing `root()` function)

```python
@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus scrape endpoint — hidden from Swagger UI."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
```

**Verify:**
```bash
uvicorn app.main:app --reload

# Make requests, then:
curl http://localhost:8000/metrics | grep aegis_requests
# Should print counter lines with current values
```

---

## Step 5 — Docker Compose + Prometheus Config

### Create `Dockerfile` (at project root)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Create `docker-compose.yml` (at project root)

```yaml
version: "3.9"

services:

  postgres:
    image: postgres:15
    container_name: aegis-postgres
    ports:
      - "5433:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: gateway
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: aegis-redis
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  gateway:
    build: .
    container_name: aegis-gateway
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:password@postgres:5432/gateway
      REDIS_HOST: redis
      REDIS_PORT: 6379
    env_file:
      - ./app/.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  prometheus:
    image: prom/prometheus:v2.51.0
    container_name: aegis-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=15d"
    depends_on:
      - gateway

  grafana:
    image: grafana/grafana:10.4.0
    container_name: aegis-grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: aegis123
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  postgres-data:
  prometheus-data:
  grafana-data:
```

### Create `prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "aegis-gateway"
    static_configs:
      - targets: ["gateway:8000"]
    metrics_path: /metrics
```

> `gateway` in targets is the Docker Compose service name — it resolves inside Docker's network to the gateway container's IP automatically.

**Verify:**
```bash
docker compose up --build -d
docker compose ps
# Open http://localhost:9090 → Status → Targets
# aegis-gateway must show State: UP
```

---

## Step 6 — Grafana Provisioning + Dashboard

### Directory structure to create

```
grafana/
├── provisioning/
│   ├── datasources/
│   │   └── prometheus.yml
│   └── dashboards/
│       └── aegis.yml
└── dashboards/
    └── aegis.json
```

### `grafana/provisioning/datasources/prometheus.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

### `grafana/provisioning/dashboards/aegis.yml`

```yaml
apiVersion: 1

providers:
  - name: "Aegis Dashboards"
    orgId: 1
    folder: "Aegis"
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    options:
      path: /var/lib/grafana/dashboards
```

### `grafana/dashboards/aegis.json`

```json
{
  "annotations": {"list": []},
  "editable": true,
  "graphTooltip": 1,
  "id": null,
  "panels": [
    {
      "id": 1,
      "title": "Request Rate by Status Code (req/sec)",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "sum(rate(aegis_requests_total[1m])) by (status_code)", "legendFormat": "HTTP {{status_code}}"}],
      "fieldConfig": {"defaults": {"unit": "reqps"}, "overrides": []}
    },
    {
      "id": 2,
      "title": "Blocked Requests by Algorithm (req/sec)",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "sum(rate(aegis_blocked_requests_total[1m])) by (algorithm)", "legendFormat": "{{algorithm}}"}],
      "fieldConfig": {"defaults": {"unit": "reqps"}, "overrides": []}
    },
    {
      "id": 3,
      "title": "Request Latency P50 / P95 / P99 (seconds)",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [
        {"expr": "histogram_quantile(0.50, sum(rate(aegis_request_duration_seconds_bucket[5m])) by (le))", "legendFormat": "P50"},
        {"expr": "histogram_quantile(0.95, sum(rate(aegis_request_duration_seconds_bucket[5m])) by (le))", "legendFormat": "P95"},
        {"expr": "histogram_quantile(0.99, sum(rate(aegis_request_duration_seconds_bucket[5m])) by (le))", "legendFormat": "P99"}
      ],
      "fieldConfig": {"defaults": {"unit": "s"}}
    },
    {
      "id": 4,
      "title": "Reputation Score Distribution P50 / P90 / P99",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [
        {"expr": "histogram_quantile(0.50, sum(rate(aegis_risk_score_distribution_bucket[5m])) by (le))", "legendFormat": "P50 score"},
        {"expr": "histogram_quantile(0.90, sum(rate(aegis_risk_score_distribution_bucket[5m])) by (le))", "legendFormat": "P90 score"},
        {"expr": "histogram_quantile(0.99, sum(rate(aegis_risk_score_distribution_bucket[5m])) by (le))", "legendFormat": "P99 score"}
      ],
      "fieldConfig": {"defaults": {"unit": "short", "min": 0, "max": 100}}
    },
    {
      "id": 5,
      "title": "Active Cooldowns Set (last 5 min)",
      "type": "stat",
      "gridPos": {"h": 4, "w": 6, "x": 0, "y": 16},
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "increase(aegis_cooldowns_set_total[5m])", "legendFormat": ""}],
      "fieldConfig": {
        "defaults": {"unit": "short", "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "yellow", "value": 5}, {"color": "red", "value": 20}]}, "color": {"mode": "thresholds"}}
      },
      "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background"}
    },
    {
      "id": 6,
      "title": "Bans Triggered (last 5 min)",
      "type": "stat",
      "gridPos": {"h": 4, "w": 6, "x": 6, "y": 16},
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "increase(aegis_bans_triggered_total[5m])", "legendFormat": ""}],
      "fieldConfig": {
        "defaults": {"unit": "short", "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "orange", "value": 1}, {"color": "red", "value": 5}]}, "color": {"mode": "thresholds"}}
      },
      "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background"}
    },
    {
      "id": 7,
      "title": "Block Reason Breakdown (last 5 min)",
      "type": "piechart",
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "targets": [{"expr": "sum by (block_reason) (increase(aegis_requests_total[5m]))", "legendFormat": "{{block_reason}}"}],
      "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "pieType": "donut"}
    }
  ],
  "refresh": "10s",
  "schemaVersion": 38,
  "tags": ["aegis", "gateway"],
  "time": {"from": "now-1h", "to": "now"},
  "timezone": "browser",
  "title": "Aegis API Gateway",
  "uid": "aegis-gateway-v1",
  "version": 1
}
```

**Verify:**
```bash
docker compose down && docker compose up -d

# Open http://localhost:3000
# Login: admin / aegis123
# Dashboards → Browse → Aegis → "Aegis API Gateway"

# Generate traffic to see data:
for i in $(seq 1 50); do curl -s -o /dev/null http://localhost:8000/; done
```

---

## PromQL Quick Reference

| Pattern | Use case |
|---|---|
| `rate(counter[1m])` | Per-second rate over last 1 min. Always use on counters, never raw value. |
| `sum(...) by (label)` | Aggregate all series, group by one label. |
| `histogram_quantile(0.99, rate(metric_bucket[5m]))` | Compute P99 from histogram. `_bucket` suffix is auto-generated. |
| `increase(counter[5m])` | Total increase in last 5 min. Use in stat panels. |

---

## Final Checklist

| # | File | Action |
|---|---|---|
| 0 | `app/config.py` | Remove duplicate field definitions |
| 1 | `requirements.txt` | Add `prometheus-client==0.20.0` |
| 2 | `app/metrics/__init__.py` | Create (empty) |
| 3 | `app/metrics/registry.py` | Create with metric objects + `get_path_group()` |
| 4 | `app/middleware/rate_limiter.py` | 4 targeted edits |
| 5 | `app/main.py` | 2 imports + `/metrics` route |
| 6 | `Dockerfile` | Create |
| 7 | `docker-compose.yml` | Create |
| 8 | `prometheus/prometheus.yml` | Create |
| 9 | `grafana/provisioning/datasources/prometheus.yml` | Create |
| 10 | `grafana/provisioning/dashboards/aegis.yml` | Create |
| 11 | `grafana/dashboards/aegis.json` | Create |

**Steps 0–5:** Verify locally without Docker.  
**Steps 6–11:** Require Docker — run `docker compose up --build -d`.
