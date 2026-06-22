from app.models.api_key import ApiKey
import secrets
from app.security.hashing import hash_password
from fastapi import HTTPException

# 1. Generate a random raw key: "aegis_" + secrets.token_urlsafe(32)
# 2. Hash it using hash_password() from security/hashing.py
# 3. Save ApiKey(name, key_hash, owner_id, rate_limit, expires_at) to DB
# 4. Return both the DB object AND the raw key (for the response)

# API CREATION
def create_api_key(db, owner_id, name, rate_limit_per_minute, expires_at):
    base = "pAegis_"
    raw_key = base + secrets.token_urlsafe(32)
    key_hash = hash_password(raw_key)
    api_key = ApiKey(
        name=name,
        key_hash=key_hash,
        owner_id=owner_id,
        rate_limit_per_minute=rate_limit_per_minute,
        expires_at=expires_at
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key, raw_key

def get_user_keys(db, owner_id):
    """Fetch all keys for a user — returns empty list if none exist"""
    return db.query(ApiKey).filter(ApiKey.owner_id == owner_id).all()


def delete_api_key(db, key_id, owner_id):
    key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.owner_id == owner_id
    ).first()

    if not key:
        raise HTTPException(status_code=404, detail="Key not found")

    db.delete(key)
    db.commit()
    return True

from app.redis.connection import redis_client
from app.models.api_key import ApiKey
from passlib.context import CryptContext
from datetime import datetime

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

CACHE_TTL = 300  # cache valid key lookups for 5 minutes



def verify_api_key(db, raw_key: str):
    """
    Validates a raw API key string.
    Returns the ApiKey ORM object if valid, None if invalid.
    
    Strategy:
    1. Check Redis cache first (fast path — avoids DB + bcrypt on repeat calls)
    2. On cache miss: query ALL active keys (reasonable if key count is small)
       and use bcrypt.checkpw() to find the matching one
    3. Cache the result in Redis for 5 minutes
    """
    if not raw_key or not raw_key.startswith("pAegis_"):
        return None

    # Fast path: check cache
    cache_key = f"apikey_valid:{raw_key[:20]}"   # use first 20 chars as cache key (never store full key)
    cached_id = redis_client.get(cache_key)
    if cached_id:
        # fetch the actual key object by ID from DB
        return db.query(ApiKey).filter(
            ApiKey.id == int(cached_id),
            ApiKey.is_active == True
        ).first()

    # Slow path: check all active, non-expired keys
    now = datetime.utcnow()
    active_keys = db.query(ApiKey).filter(
        ApiKey.is_active == True,
        (ApiKey.expires_at == None) | (ApiKey.expires_at > now)
    ).all()

    for api_key in active_keys:
        if pwd_context.verify(raw_key, api_key.key_hash):
            # Cache this result so subsequent requests skip the bcrypt loop
            redis_client.set(cache_key, api_key.id, ex=CACHE_TTL)
            return api_key

    return None   # no match found
