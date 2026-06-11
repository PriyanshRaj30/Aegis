from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ApiKeyCreate(BaseModel):
    name: str
    rate_limit_per_minute: int = 60
    expires_at: Optional[datetime] = None

class ApiKeyCreateResponse(BaseModel):
    id: int
    name: str
    raw_key: str           # ← show this once, then it's gone forever
    rate_limit_per_minute: int
    created_at: datetime
    expires_at: Optional[datetime]

class ApiKeyResponse(BaseModel):
    id: int
    name: str
    rate_limit_per_minute: int
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True
