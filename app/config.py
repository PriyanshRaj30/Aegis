from pydantic_settings import BaseSettings
from pathlib import Path

# Resolves to the .env file sitting next to this config.py (inside app/)
ENV_FILE = Path(__file__).parent / ".env"

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    DATABASE_URL: str

    class Config:
        env_file = str(ENV_FILE)

settings = Settings()