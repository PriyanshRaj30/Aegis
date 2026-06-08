from jose import jwt
from datetime import datetime
from datetime import timedelta

SECRET_KEY = "super-secret"

ALGORITHM = "HS256"


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
# i.e.
# {
#   "user_id": 1,
#   "role": "ADMIN",
#   "exp": 123456789
# }


save_user(
    email,
    hashed,
    role
)