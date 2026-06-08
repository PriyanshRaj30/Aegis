from pydantic import BaseModel
from app.models.roles import Role

class UserRegister(BaseModel):

    email: str

    password: str

    role: Role

class UserLogin(BaseModel):

    email: str

    password: str

class TokenResponse(BaseModel):

    access_token: str

    token_type: str