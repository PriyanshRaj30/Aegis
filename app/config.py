from pydantic_settings import BaseSettings
from pathlib import Path

# Resolves to the .env file sitting next to this config.py (inside app/)
ENV_FILE = Path(__file__).parent / ".env"

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    DATABASE_URL: str

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    RISK_THROTTLE_THRESHOLD: int
    RISK_BAN_THRESHOLD: int
    BAN_DURATION_SECONDS: int

    RATE_LIMIT_REQUESTS: int
    RATE_LIMIT_WINDOW_SECONDS: int

    class Config:
        env_file = str(ENV_FILE)

settings = Settings()
