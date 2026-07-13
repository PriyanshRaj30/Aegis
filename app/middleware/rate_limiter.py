from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.rate_limiter import check_rate_limit
from app.config import settings

from app.services.risk_engine import (
    is_banned,
    is_key_banned,
    add_risk_points,
    evaluate_risk,
    get_risk_score,
)
from app.database.connection import SessionLocal
from app.services.audit_service import create_log

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



class RateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        # --- Identify both dimensions of the caller ---
        ip = request.client.host
        api_key_id = request.headers.get("X-API-Key", "") or ""

        method = request.method
        path_group = get_path_group(request.url.path)
        start_time = time_module.time()
        tokens_remaining = 0


        api_key_id = request.headers.get("X-API-Key", "") or ""

        method = request.method
        path_group = get_path_group(request.url.path)
        start_time = time_module.time()
        tokens_remaining = 0


        # --- Ban check: IP and API key are checked independently ---
        if is_banned(ip):
            BLOCKED_REQUESTS_TOTAL.labels(algorithm="ban").inc()
            REQUESTS_TOTAL.labels(method=method, path_group=path_group,
                status_code="403", block_reason="ip_banned").inc()
            REQUEST_DURATION_SECONDS.labels(method=method, path_group=path_group).observe(
                time_module.time() - start_time)
            return JSONResponse(status_code=403, content={"detail": "IP temporarily banned"})

        if api_key_id and is_key_banned(api_key_id):
            BLOCKED_REQUESTS_TOTAL.labels(algorithm="ban").inc()
            REQUESTS_TOTAL.labels(method=method, path_group=path_group,
                status_code="403", block_reason="key_banned").inc()
            REQUEST_DURATION_SECONDS.labels(method=method, path_group=path_group).observe(
                time_module.time() - start_time)
            return JSONResponse(status_code=403, content={"detail": "API key temporarily banned"})


        # --- Rate limit check (sliding window, per-IP + per-key) ---
        try:
            allowed = check_rate_limit(
                user_id=ip,
                api_key_id=api_key_id,   # was always "" before — now real key
                action="generic"
            )
        except Exception:
            allowed = True

        # --- Rate limit exceeded: score both dimensions atomically ---
        if not allowed:
            add_risk_points(f"ip:{ip}", settings.WEIGHT_RATE_LIMIT_SLIDING)
            if api_key_id:
                add_risk_points(f"key:{api_key_id}", settings.WEIGHT_RATE_LIMIT_SLIDING)

            risk_status = evaluate_risk(ip=ip, api_key_id=api_key_id or None)

            if risk_status == "banned":
                BANS_TRIGGERED_TOTAL.inc()

            BLOCKED_REQUESTS_TOTAL.labels(algorithm="sliding_window").inc()
            REQUESTS_TOTAL.labels(method=method, path_group=path_group,
                status_code="429", block_reason="sliding_window").inc()
            REQUEST_DURATION_SECONDS.labels(method=method, path_group=path_group).observe(
                time_module.time() - start_time)

            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "risk_status": risk_status
                }
            )

        # --- Let the request through ---
        response = await call_next(request)

        # --- Audit log — write to DB ---
        try:
            db = SessionLocal()
            try:
                create_log(
                    db=db,
                    ip=ip,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    risk_score=get_risk_score(f"ip:{ip}"),
                    rate_limited=(response.status_code == 429)
                )
            finally:
                db.close()
        except Exception:
            pass  # never let logging crash a request

        # --- Post-response risk scoring: both IP and API key dimensions ---
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
            pass  # Redis down → skip scoring, don't crash

        return response
