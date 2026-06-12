from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime
from app.database.connection import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id          = Column(Integer, primary_key=True)
    ip_address  = Column(String, nullable=False)
    method      = Column(String, nullable=False)       # "GET", "POST" etc.
    path        = Column(String, nullable=False)       # "/auth/login"
    status_code = Column(Integer, nullable=False)
    risk_score  = Column(Float, default=0.0)
    rate_limited = Column(Boolean, default=False)
    timestamp   = Column(DateTime, default=datetime.utcnow)
