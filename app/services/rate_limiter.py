from time import time
import uuid
from app.config import settings
from app.redis.connection import redis_client

def check_rate_limit(user_id, api_key_id, action):
    key = f"rate_limit:{user_id}:{api_key_id}:{action}"

    current_time_ms = int(time() * 1000)

    window_ms = (settings.RATE_LIMIT_WINDOW_SECONDS * 1000)

    limit = settings.RATE_LIMIT_REQUESTS

    window_start = current_time_ms - window_ms

    redis_client.zremrangebyscore(key, "-inf", window_start)

    request_count = redis_client.zcard(key)

    if request_count >= limit:
        return False

    member = f"{current_time_ms}:{uuid.uuid4()}"

    redis_client.zadd(key, {member: current_time_ms})

    redis_client.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS + 1)

    return True