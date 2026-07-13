from pydantic_settings import BaseSettings
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    DATABASE_URL: str

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    BAN_DURATION_SECONDS: int

    RATE_LIMIT_REQUESTS: int
    RATE_LIMIT_WINDOW_SECONDS: int

    TOKEN_BUCKET_CAPACITY: int
    TOKEN_BUCKET_REFILL_RATE: float

    COOLDOWN_DURATION_SECONDS: int

    # Reputation Engine
    RISK_DECAY_RATE: float = 0.95

    # Risk Thresholds
    RISK_THROTTLE_THRESHOLD: int
    RISK_LIGHT_THROTTLE_THRESHOLD: int
    RISK_HEAVY_THROTTLE_THRESHOLD: int
    RISK_BAN_THRESHOLD: int

    # Signal Weights
    WEIGHT_RATE_LIMIT_SLIDING: float
    WEIGHT_RATE_LIMIT_TOKEN: float
    WEIGHT_BURST_DETECTED: float
    WEIGHT_INVALID_API_KEY: float
    WEIGHT_STATUS_401: float
    WEIGHT_STATUS_403: float
    WEIGHT_STATUS_404: float

    class Config:
        env_file = str(ENV_FILE)

settings = Settings()
