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


# def verify_api_key(db, raw_key):

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

    
