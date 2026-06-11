from app.redis.connection import redis_client
from app.config import settings


def get_risk_score(identifier: str) -> float:
    key = f"risk:{identifier}"
    value = redis_client.get(key) #????????      # returns None if key doesn't exist
    if value is None:
        return 0.0
    return float(value)

def add_risk_points(identifier: str, points: float):
    key = f"risk:{identifier}"
    current = get_risk_score(identifier)        # get existing score (or 0.0)
    new_score = min(100.0, current + points)    # cap at 100
    redis_client.set(key, new_score, ex=3600)   # save, expire in 1 hour

def is_banned(identifier: str) -> bool:
    key = f"banned:{identifier}"
    return redis_client.exists(key) > 0

def ban_ip(identifier: str, duration_seconds: int):
    key = f"banned:{identifier}"
    redis_client.set(key, 1, ex=duration_seconds)


def evaluate_risk(identifier: str) -> str:
    score = get_risk_score(identifier)
    if score >= settings.RISK_BAN_THRESHOLD:
        ban_ip(identifier, settings.BAN_DURATION_SECONDS)
        return "banned"
    if score >= settings.RISK_THROTTLE_THRESHOLD:
        # dont ban yet, reduce it !!!!
        return "throttle"
    return "allow"
