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


class RateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        # --- Identify both dimensions of the caller ---
        ip = request.client.host
        api_key_id = request.headers.get("X-API-Key", "") or ""

        # --- Ban check: IP and API key are checked independently ---
        if is_banned(ip):
            return JSONResponse(
                status_code=403,
                content={"detail": "IP temporarily banned"}
            )
        if api_key_id and is_key_banned(api_key_id):
            return JSONResponse(
                status_code=403,
                content={"detail": "API key temporarily banned"}
            )

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
            points = 0.0
            if response.status_code == 404:
                points = settings.WEIGHT_STATUS_404
            elif response.status_code == 401:
                points = settings.WEIGHT_STATUS_401
            elif response.status_code == 403:
                points = settings.WEIGHT_STATUS_403

            if points:
                add_risk_points(f"ip:{ip}", points)
                if api_key_id:
                    add_risk_points(f"key:{api_key_id}", points)

            evaluate_risk(ip=ip, api_key_id=api_key_id or None)
        except Exception:
            pass  # Redis down → skip scoring, don't crash

        return response
