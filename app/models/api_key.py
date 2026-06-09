from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.connection import Base

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)

    name = Column(String, nullable=False)          # human label e.g. "my-app-key"

    key_hash = Column(String, unique=True, nullable=False)  # bcrypt hash of the raw key

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    rate_limit_per_minute = Column(Integer, default=60)    # per-key rate limit

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    expires_at = Column(DateTime, nullable=True)   # None = never expires