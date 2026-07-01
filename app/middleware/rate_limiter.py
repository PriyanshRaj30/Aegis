from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.rate_limiter import check_rate_limit
from app.services.token_bucket import check_token_bucket
from app.services.burst_detector import detect_burst
from app.services.cooldown import is_in_cooldown, set_cooldown
from app.services.risk_engine import is_banned, add_risk_points, evaluate_risk, get_risk_score
from app.services.api_key_service import verify_api_key

from app.services.risk_engine import (
    is_banned,
    is_key_banned,
    add_risk_points,
    evaluate_risk,
    get_risk_score,
)
from app.database.connection import SessionLocal
from app.services.audit_service import create_log
from app.config import settings


# Paths that skip rate limiting entirely
SKIP_PATHS = {"/metrics", "/docs", "/openapi.json", "/redoc"}



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
        # Skip monitoring and docs paths
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        ip = request.client.host

        # ────────────────────────────────────────────────────────────
        # CHECK 1: Hard ban (cheapest check — Redis EXISTS, ~0.1ms)
        # If this IP is banned, reject immediately before any other work.
        # ────────────────────────────────────────────────────────────
        
        if is_banned(ip):
            return JSONResponse(
                status_code=403,
                headers={"X-Aegis-Block-Reason": "ip_banned"},
                content={"detail": "Your IP has been temporarily banned due to abuse."}
            )

        # ────────────────────────────────────────────────────────────
        # CHECK 2: Cooldown (Redis TTL, ~0.1ms)
        # Softer than a ban. Client entered cooldown due to burst.
        # ────────────────────────────────────────────────────────────
        cooldown_ttl = is_in_cooldown(ip)
        if cooldown_ttl:
            return JSONResponse(
                status_code=429,
                headers={
                    "Retry-After": str(cooldown_ttl),
                    "X-Aegis-Block-Reason": "cooldown"
                },
                content={
                    "detail": f"Too many requests. Please wait {cooldown_ttl} seconds.",
                    "retry_after": cooldown_ttl
                }
            )

        # --- Rate limit exceeded: score both dimensions atomically ---
        if not allowed:
            add_risk_points(f"ip:{ip}", settings.WEIGHT_RATE_LIMIT_SLIDING)
            if api_key_id:
                add_risk_points(f"key:{api_key_id}", settings.WEIGHT_RATE_LIMIT_SLIDING)

            risk_status = evaluate_risk(ip=ip, api_key_id=api_key_id or None)
        # ────────────────────────────────────────────────────────────
        # CHECK 3: API Key validation (DB query, ~5-15ms)
        # Only runs if IP passed checks 1 and 2.
        # If a valid key is found → use per-key rate limit quota.
        # If an invalid key is provided → reject 401.
        # If no key is provided → fall back to IP-based limits.
        # ────────────────────────────────────────────────────────────
        raw_key = request.headers.get("X-API-Key")
        api_key_obj = None
        identifier = f"ip:{ip}"              # default: identify by IP
        rate_limit = settings.RATE_LIMIT_REQUESTS  # default quota

        if raw_key:
            db = SessionLocal()
            try:
                api_key_obj = verify_api_key(db, raw_key)
            finally:
                db.close()

            if api_key_obj is None:
                # A key was provided but it's invalid or expired
                add_risk_points(ip, 15)       # bad key attempt → add risk
                return JSONResponse(
                    status_code=401,
                    headers={"X-Aegis-Block-Reason": "invalid_api_key"},
                    content={"detail": "Invalid or expired API key."}
                )

            # Valid key found → switch identifier and use per-key rate limit
            identifier = f"key:{api_key_obj.id}"
            rate_limit = api_key_obj.rate_limit_per_minute

        # ────────────────────────────────────────────────────────────
        # CHECK 4: IP Reputation (Redis GET, ~0.1ms)
        # Read the current risk score. If in throttle zone, halve the quota.
        # This doesn't block — it just makes life harder for risky IPs.
        # ────────────────────────────────────────────────────────────
        risk_score = get_risk_score(ip)
        if risk_score >= settings.RISK_THROTTLE_THRESHOLD:
            rate_limit = max(1, rate_limit // 2)   # halve the effective quota

        # ────────────────────────────────────────────────────────────
        # CHECK 5: Sliding Window (Redis ZSET, ~0.2ms)
        # "How many requests in the last N seconds?"
        # Uses your existing check_rate_limit() — no changes needed there.
        # ────────────────────────────────────────────────────────────
        sliding_allowed = check_rate_limit(
            user_id=identifier,
            api_key_id=str(api_key_obj.id) if api_key_obj else "",
            action="generic",
            limit_override=rate_limit      # pass the (possibly halved) limit
        )
        if not sliding_allowed:
            add_risk_points(ip, 20)
            evaluate_risk(ip)
            return JSONResponse(
                status_code=429,
                headers={"X-Aegis-Block-Reason": "sliding_window"},
                content={"detail": "Rate limit exceeded. Too many requests in the current window."}
            )

        # ────────────────────────────────────────────────────────────
        # CHECK 6: Token Bucket (Redis HASH + Lua, ~0.3ms)
        # "Is the burst capacity exhausted?"
        # Runs after sliding window to catch clients that game the window boundary.
        # ────────────────────────────────────────────────────────────
        bucket_allowed, tokens_remaining = check_token_bucket(identifier)
        if not bucket_allowed:
            add_risk_points(ip, 15)
            evaluate_risk(ip)
            return JSONResponse(
                status_code=429,
                headers={"X-Aegis-Block-Reason": "token_bucket"},
                content={"detail": "Request rate too high. Token bucket exhausted."}
            )

        # --- Let the request through ---
        response = await call_next(request)

        # --- Audit log — write to DB ---
        # ────────────────────────────────────────────────────────────
        # CHECK 7: Burst Detector (Redis INCR, ~0.1ms)
        # "More than N requests in the current second?"
        # This is the last gate — cheapest write, catches sub-second floods.
        # On burst: add heavy risk points AND set cooldown. Don't block this
        # specific request — the cooldown gates the NEXT request.
        # ────────────────────────────────────────────────────────────
        if detect_burst(ip):
            add_risk_points(ip, 35)
            set_cooldown(ip)               # uses settings.COOLDOWN_DURATION_SECONDS
            risk_result = evaluate_risk(ip)
            # Note: we still allow THIS request through. The cooldown blocks the next one.
            # This is intentional — we don't penalize the exact request that triggered detection,
            # just immediately gate all future ones.

        # ────────────────────────────────────────────────────────────
        # All checks passed — forward to the actual handler
        # ────────────────────────────────────────────────────────────
        response = await call_next(request)

        # ────────────────────────────────────────────────────────────
        # POST-RESPONSE: Audit log (synchronous DB write for now)
        # Issue #2 (Kafka) will replace this with an async event publish.
        # ────────────────────────────────────────────────────────────
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
                    risk_score=get_risk_score(ip),
                    rate_limited=(response.status_code == 429)
                )
            finally:
                db.close()
        except Exception:
            pass   # never crash a request over an audit log failure

        # --- Post-response risk scoring: both IP and API key dimensions ---
        # ────────────────────────────────────────────────────────────
        # POST-RESPONSE: Risk scoring based on response status
        # ────────────────────────────────────────────────────────────
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
                add_risk_points(ip, 5)     # endpoint scanning/enumeration
            elif response.status_code == 401:
                add_risk_points(ip, 10)    # credential failure
            elif response.status_code == 403:
                add_risk_points(ip, 5)     # hitting restricted resources
            evaluate_risk(ip)
        except Exception:
            pass   # Redis down → skip, don't crash

        # ────────────────────────────────────────────────────────────
        # Add informational headers to the response
        # ────────────────────────────────────────────────────────────
        response.headers["X-RateLimit-Remaining-Tokens"] = str(tokens_remaining)
        response.headers["X-RateLimit-Risk-Score"] = str(int(risk_score))

        return response
