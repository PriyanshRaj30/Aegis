import time
from app.redis.connection import redis_client
from app.config import settings


def detect_burst(identifier: str) -> bool:
    current_second = int(time.time())
    key = f"burst:{identifier}:{current_second}"

    count = redis_client.incr(key)           
    redis_client.expire(key, 2)              

    return count > settings.BURST_THRESHOLD
