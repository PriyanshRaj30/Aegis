from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.rate_limiter import check_rate_limit
from app.config import settings

class RateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        # 1. Identify the caller — use IP address for now
        identifier = request.client.host

        # 2. Check the rate limit
        try:
            allowed = check_rate_limit(
                user_id=identifier,
                api_key_id="",
                action="generic"
            )
        except Exception:
            allowed = True  # Redis down → fail open, don't block users
            
        # 3. Block if over limit
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Try again later.",
                    "limit": settings.RATE_LIMIT_REQUESTS,
                    "window_seconds": settings.RATE_LIMIT_WINDOW_SECONDS,
                }
            )

        # 4. Otherwise let the request through
        response = await call_next(request)
        return response
