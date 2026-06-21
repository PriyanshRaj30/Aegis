import time
from app.redis.connection import redis_client
from app.config import settings

# Define the Lua script as a module-level string constant.
# redis-py will register it with Redis and call it by SHA hash for efficiency.
TOKEN_BUCKET_SCRIPT = """
local data        = redis.call('HMGET', KEYS[1], 'tokens', 'last_refill')
local max_tokens  = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now         = tonumber(ARGV[3])

local tokens      = tonumber(data[1]) or max_tokens
local last_refill = tonumber(data[2]) or now

local elapsed     = now - last_refill
local new_tokens  = math.min(max_tokens, tokens + elapsed * refill_rate)

if new_tokens < 1 then
    redis.call('HMSET', KEYS[1], 'tokens', new_tokens, 'last_refill', now)
    redis.call('EXPIRE', KEYS[1], 3600)
    return {0, 0}
end

new_tokens = new_tokens - 1
redis.call('HMSET', KEYS[1], 'tokens', new_tokens, 'last_refill', now)
redis.call('EXPIRE', KEYS[1], 3600)
return {1, math.floor(new_tokens)}
"""

# Register the script once at import time.
# redis-py's register_script() returns a callable Script object.
# Under the hood it uses EVALSHA (cached) with a fallback to EVAL.
_token_bucket_script = redis_client.register_script(TOKEN_BUCKET_SCRIPT)


def check_token_bucket(identifier: str, max_tokens: int = None, refill_rate: float = None) -> tuple[bool, int]:
    """
    Returns: (allowed: bool, tokens_remaining: int)
    
    identifier  — the key to use (e.g. "ip:1.2.3.4" or "key:uuid")
    max_tokens  — bucket capacity; defaults to settings value
    refill_rate — tokens per second; defaults to settings value
    """
    if max_tokens is None:
        max_tokens = settings.TOKEN_BUCKET_CAPACITY
    if refill_rate is None:
        refill_rate = settings.TOKEN_BUCKET_REFILL_RATE

    key = f"token_bucket:{identifier}"
    now = time.time()  # float, e.g. 1718000059.432

    result = _token_bucket_script(
        keys=[key],
        args=[max_tokens, refill_rate, now]
    )
    # result is [allowed_int, remaining_int]
    allowed = int(result[0]) == 1
    remaining = int(result[1])
    return allowed, remaining
