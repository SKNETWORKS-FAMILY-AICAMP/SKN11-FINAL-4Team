from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from dotenv import load_dotenv

from .models import JWTPayload

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

security = HTTPBearer()

def create_access_token(user_data: Dict) -> str:
    to_encode = user_data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow()
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[Dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload

def generate_jwt_payload(user_info: Dict, provider: str) -> Dict:
    is_business = False
    business_features = {}
    
    if provider == "instagram":
        account_type = user_info.get("account_type", "PERSONAL")
        is_business = account_type in ["BUSINESS", "CREATOR"]
        business_features = {
            "insights": is_business,
            "content_publishing": is_business,
            "message_management": is_business,
            "comment_management": True
        }
    
    payload = {
        "sub": user_info.get("id"),
        "email": user_info.get("email"),
        "name": user_info.get("name"),
        "provider": provider,
        "company": f"{provider.title()} Business User" if is_business else f"{provider.title()} User",
        "groups": ["business", "user"] if is_business else ["user"],
        "permissions": [
            "post:read", "post:write", "model:read", "model:write", 
            "insights:read", "business:manage"
        ] if is_business else ["post:read", "model:read"],
    }
    
    if provider == "instagram":
        payload["instagram"] = {
            "username": user_info.get("username"),
            "account_type": user_info.get("account_type"),
            "is_business_verified": is_business,
            "business_features": business_features
        }
    
    return payload