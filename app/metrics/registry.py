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
