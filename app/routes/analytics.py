from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.auth import require_role
from app.services.audit_service import get_summary

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
def analytics_summary(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("ADMIN"))
):
    return get_summary(db)
