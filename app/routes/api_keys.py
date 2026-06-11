from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.auth import get_current_user

from app.models.user import User

from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyResponse
)

from app.services.api_key_service import (
    create_api_key,
    get_user_keys,
    delete_api_key
)

router = APIRouter(
    prefix="/api-keys",
    tags=["API Keys"]
)


@router.post(
    "",
    response_model=ApiKeyCreateResponse
)
def create_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    api_key, raw_key = create_api_key(
        db=db,
        owner_id=current_user.id,
        name=payload.name,
        rate_limit_per_minute=payload.rate_limit_per_minute,
        expires_at=payload.expires_at
    )
    return {
        "id": api_key.id,
        "name": api_key.name,
        "raw_key": raw_key,
        "rate_limit_per_minute": api_key.rate_limit_per_minute,
        "created_at": api_key.created_at,
        "expires_at": api_key.expires_at,
    }


@router.get(
    "",
    response_model=List[ApiKeyResponse]
)
def list_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_user_keys(
        db=db,
        owner_id=current_user.id
    )


@router.delete("/{key_id}")
def remove_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    delete_api_key(
        db=db,
        owner_id=current_user.id,
        key_id=key_id
    )

    return {
        "message": "API key deleted successfully"
    }