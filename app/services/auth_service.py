from app.models.user import User
from app.security.hashing import hash_password, verify_password
from app.security.jwt_handler import create_access_token
from app.database.connection import get_db
from datetime import datetime

def register_user(db, email, password, role):
    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise Exception("Email already registered")
    
    hashed_password = hash_password(password)
    
    user = User(
        email=email,
        password_hash=hashed_password,
        role=role
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


def login_user(db, email, password):
    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        raise Exception("Invalid credentials")

    if not verify_password(
        password,
        user.password_hash
    ):
        raise Exception("Invalid credentials")

    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }