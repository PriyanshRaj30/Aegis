from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.schemas.user import (
    UserRegister,
    UserLogin,
    TokenResponse
)

from app.services.auth_service import (
    register_user,
    login_user
)

from app.database.connection import get_db

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/register", response_model=TokenResponse)
def register(
    user_register: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new user. Send JSON: {"email": "...", "password": "...", "role": "ADMIN"}
    """
    try:
        result = register_user(
            db,
            user_register.email,
            user_register.password,
            user_register.role
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)   # shows real error so you can debug
        )


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login — use Swagger UI 'Authorize' button.
    Enter your email in the 'username' field (OAuth2 standard naming).
    """
    try:
        result = login_user(
            db,
            form_data.username,  # Swagger sends email as 'username'
            form_data.password
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )