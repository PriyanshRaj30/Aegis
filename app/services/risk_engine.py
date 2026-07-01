import time
from app.redis.connection import redis_client
from app.config import settings

# ---------------------------------------------------------------------------
# Lua script: atomically decays the current score and adds new points.
# Executed as a single Redis command — no concurrent read/modify/write race.
# ---------------------------------------------------------------------------
_ADD_RISK_SCRIPT = """
local key          = KEYS[1]
local points       = tonumber(ARGV[1])
local decay_rate   = tonumber(ARGV[2])
local now          = tonumber(ARGV[3])
local max_risk     = tonumber(ARGV[4])

local data         = redis.call('HMGET', key, 'score', 'last_updated')
local last_score   = tonumber(data[1]) or 0
local last_updated = tonumber(data[2]) or now

-- Exponential decay based on elapsed minutes
local elapsed_minutes = (now - last_updated) / 60.0
local decayed = last_score * (decay_rate ^ elapsed_minutes)
if decayed < 0.1 then decayed = 0 end

local new_score = math.min(max_risk, decayed + points)

redis.call('HSET', key, 'score', new_score, 'last_updated', now)
redis.call('EXPIRE', key, 86400)
return tostring(new_score)
"""

_add_risk_script = redis_client.register_script(_ADD_RISK_SCRIPT)


def get_decayed_score(identifier: str) -> float:
    """
    Retrieves the decayed risk score for a specific identifier (IP or API key).
    Calculates decay on the fly based on elapsed time.
    """
    key = f"risk:{identifier}"
    data = redis_client.hgetall(key)

    if not data:
        return 0.0

    last_score = float(data.get("score", 0.0))
    last_updated = float(data.get("last_updated", time.time()))

    # Calculate elapsed time in minutes
    elapsed_minutes = (time.time() - last_updated) / 60.0

    # Apply exponential decay: score * (decay_rate ^ elapsed_minutes)
    decayed_score = last_score * (settings.RISK_DECAY_RATE ** elapsed_minutes)

    # If the score has decayed to a negligible value, clean up the key
    if decayed_score < 0.1:
        redis_client.delete(key)
        return 0.0

    redis_client.hset(
        key,
        mapping={
            "score": decayed_score,
            "last_updated": time.time()
        }
    )

    return round(decayed_score, 2)


def get_risk_score(identifier: str) -> float:
    """
    Returns the current decayed risk score without modifying it.
    Convenience wrapper used by audit logging.
    """
    return get_decayed_score(identifier)


def add_risk_points(identifier: str, points: float):
    """
    Atomically applies decay to the current score, adds new points, caps at 100,
    and saves the updated score with the current timestamp.

    Uses a Lua script so the read-decay-add-write sequence is executed as a
    single atomic Redis operation, eliminating the race condition where two
    concurrent callers both read the same score and one update is lost.
    """
    key = f"risk:{identifier}"
    _add_risk_script(
        keys=[key],
        args=[points, settings.RISK_DECAY_RATE, time.time(), 100.0]
    )


# ---------------------------------------------------------------------------
# Ban helpers — IP and API Key are banned independently
# ---------------------------------------------------------------------------

def is_banned(ip: str) -> bool:
    """Checks if the IP address is currently banned."""
    return redis_client.exists(f"banned:ip:{ip}") > 0


def is_key_banned(api_key_id: str) -> bool:
    """Checks if the API key is currently banned."""
    return redis_client.exists(f"banned:key:{api_key_id}") > 0


def ban_ip(ip: str, duration_seconds: int):
    """Bans an IP address for a specific duration."""
    redis_client.set(f"banned:ip:{ip}", 1, ex=duration_seconds)


def ban_key(api_key_id: str, duration_seconds: int):
    """Bans an API key for a specific duration."""
    redis_client.set(f"banned:key:{api_key_id}", 1, ex=duration_seconds)


def evaluate_risk(ip: str, api_key_id: str = None) -> str:
    """
    Evaluates the combined risk score of the IP and the API Key (multi-dimensional).
    If the score exceeds the ban threshold, it bans both the IP and the API key.

    Returns: "allow", "throttle_light", "throttle_heavy", or "banned"
    """
    # 1. Fetch decayed scores for both IP and API Key
    ip_score = get_decayed_score(f"ip:{ip}")
    key_score = get_decayed_score(f"key:{api_key_id}") if api_key_id else 0.0

    # 2. Take the maximum of both dimensions
    max_score = max(ip_score, key_score)

    # 3. Evaluate thresholds
    if max_score >= settings.RISK_BAN_THRESHOLD:
        # Ban both the originating IP and the offending API key
        ban_ip(ip, settings.BAN_DURATION_SECONDS)
        if api_key_id:
            ban_key(api_key_id, settings.BAN_DURATION_SECONDS)
        return "banned"

    if max_score >= settings.RISK_HEAVY_THROTTLE_THRESHOLD:
        return "throttle_heavy"

    if max_score >= settings.RISK_LIGHT_THROTTLE_THRESHOLD:
        return "throttle_light"

    return "allow"
