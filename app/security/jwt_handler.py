from jose import jwt
from datetime import datetime
from datetime import timedelta
from app.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM


def create_access_token(data):

    payload = data.copy()
    
    # expiration timestamp
    payload["exp"] = (
        datetime.utcnow()
        + timedelta(hours=1)
    )

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

def decode_access_token(token):

    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM]
    )