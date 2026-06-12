from sqlalchemy import func
from app.models.audit_log import AuditLog

def create_log(db, ip, method, path, status_code, risk_score=0.0, rate_limited=False):
    log = AuditLog(
        ip_address=ip,
        method=method,
        path=path,
        status_code=status_code,
        risk_score=risk_score,
        rate_limited=rate_limited
    )
    db.add(log)
    db.commit()



def get_summary(db):
    total   = db.query(AuditLog).count()
    blocked = db.query(AuditLog).filter(
        AuditLog.status_code.in_([429, 403])
    ).count()
    unique_ips = db.query(func.count(func.distinct(AuditLog.ip_address))).scalar()
    avg_risk   = db.query(func.avg(AuditLog.risk_score)).scalar() or 0.0

    # Top 5 most hit paths
    top_paths = (
        db.query(AuditLog.path, func.count(AuditLog.path).label("count"))
        .group_by(AuditLog.path)
        .order_by(func.count(AuditLog.path).desc())
        .limit(5)
        .all()
    )

    return {
        "total_requests": total,
        "blocked_requests": blocked,
        "unique_ips": unique_ips,
        "avg_risk_score": round(float(avg_risk), 2),
        "top_paths": [{"path": p, "count": c} for p, c in top_paths]
    }
