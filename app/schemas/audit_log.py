from pydantic import BaseModel
from datetime import datetime

class AuditLogResponse(BaseModel):
    id: int
    ip_address: str
    method: str
    path: str
    status_code: int
    risk_score: float
    rate_limited: bool
    timestamp: datetime

    class Config:
        from_attributes = True


class AnalyticsSummary(BaseModel):
    total_requests: int
    blocked_requests: int       # status 429 or 403
    unique_ips: int
    avg_risk_score: float
    top_paths: list             # list of {"path": str, "count": int}
