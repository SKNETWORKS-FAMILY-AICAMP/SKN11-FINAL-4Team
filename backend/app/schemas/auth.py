from pydantic import BaseModel, EmailStr
from typing import Optional


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_uuid: Optional[str] = None


class UserRegister(BaseModel):
    provider_id: str
    provider: str
    user_name: str
    email: EmailStr
