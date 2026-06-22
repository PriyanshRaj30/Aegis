from app.redis.connection import redis_client
from app.config import settings


def is_in_cooldown(identifier: str) -> int:
    """
    Returns the remaining cooldown TTL in seconds, or 0 if not in cooldown.
    
    We return TTL (not just bool) so the middleware can set the Retry-After header.
    Redis TTL returns -2 if key doesn't exist, -1 if key has no expiry.
    """
    ttl = redis_client.ttl(f"cooldown:{identifier}")
    return max(0, ttl)   # normalize -2 and -1 to 0


def set_cooldown(identifier: str, duration_seconds: int = None):
    """
    Puts an identifier into cooldown for duration_seconds.
    Uses settings.COOLDOWN_DURATION_SECONDS if not specified.
    """
    if duration_seconds is None:
        duration_seconds = settings.COOLDOWN_DURATION_SECONDS

    redis_client.set(
        f"cooldown:{identifier}",
        1,                      # value doesn't matter; presence = in cooldown
        ex=duration_seconds     # Redis auto-deletes after this many seconds
    )
