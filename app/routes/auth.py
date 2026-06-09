# POST /auth/register — accepts UserRegister, calls auth_service.register_user(), returns TokenResponse
# POST /auth/login — accepts UserLogin, calls auth_service.login_user(), returns TokenResponse

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi import HTTPException

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
def register(user_register: UserRegister,
db: Session = Depends(get_db)):
    """
    Register a new user (employee or admin)
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
            detail="Email already registered"
        )

@router.post("/login", response_model=TokenResponse)
def login(user_login: UserLogin,
db: Session = Depends(get_db)):
    """
    Login an existing user
    """
    try:
        result = login_user(
            db, 
            user_login.email,
            user_login.password
        )
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="Invalid credentials"
        )