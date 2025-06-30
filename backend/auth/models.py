from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, List
from datetime import datetime

class SocialLoginRequest(BaseModel):
    provider: str
    code: Optional[str] = None
    redirect_uri: Optional[str] = None
    state: Optional[str] = None
    user_info: Optional[Dict] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict

class UserInfo(BaseModel):
    id: str
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    provider: str
    username: Optional[str] = None
    account_type: Optional[str] = None
    
class JWTPayload(BaseModel):
    sub: str
    email: Optional[str] = None
    name: Optional[str] = None
    provider: str
    company: Optional[str] = None
    groups: List[str] = []
    permissions: List[str] = []
    instagram: Optional[Dict] = None
    exp: int
    iat: int