from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import BaseModel

from app.config import settings
from app.models.user import User
from app.database.connection import get_db
from sqlalchemy.orm import Session
from jose import JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


class TokenData(BaseModel):
    id: str = None
    email: str = None
    role: str = None


def get_current_user(db: Session = Depends(get_db),
token: str = Depends(oauth2_scheme)):
    """
    Dependency to get the current user from a JWT token.
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        role: str = payload.get("role")

        if user_id is None or email is None:
            raise credentials_exception

        token_data = TokenData(id=user_id, email=email, role=role)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if user is None:
        raise credentials_exception

    return user


def require_role(required_role: str):
    """
    Dependency to ensure the user has a specific role.
    """
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != (required_role.upper()):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker


def require_admin():
    """
    Convenience dependency to ensure the user is an admin.
    """
    return require_role("ADMIN")