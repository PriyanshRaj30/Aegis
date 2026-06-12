from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.rate_limiter import check_rate_limit
from app.config import settings

from app.services.risk_engine import (
    is_banned,
    add_risk_points,
    evaluate_risk,
    get_risk_score
)
from app.database.connection import SessionLocal
from app.services.audit_service import create_log

class RateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        # Identify the caller — use IP address for now
        identifier = request.client.host

        # Already banned?
        if is_banned(identifier):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "IP temporarily banned"
                }
            )

        try:
            allowed = check_rate_limit(
                user_id=identifier,
                api_key_id="",
                action="generic"
            )
        except Exception:
            allowed = True


        # Rate limit exceeded
        if not allowed:

            add_risk_points(
                identifier,
                20
            )

            risk_status = evaluate_risk(
                identifier
            )

            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "risk_status": risk_status
                }
            )

        # Let the request through
        response = await call_next(request)


        # Audit log — write to DB
        try:
            db = SessionLocal()
            try:
                create_log(
                    db=db,
                    ip=identifier,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    risk_score=get_risk_score(identifier),
                    rate_limited=(response.status_code == 429)
                )
            finally:
                db.close()
        except Exception:
            pass  # never let logging crash a request

        # Post-response risk scoring
        try:
            if response.status_code == 404:
                add_risk_points(identifier, 5)
            elif response.status_code == 401:
                add_risk_points(identifier, 10)

            evaluate_risk(identifier)
        except Exception:
            pass  # Redis down → skip scoring, don't crash

        return response
