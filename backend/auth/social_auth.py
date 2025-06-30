import httpx
import os
from typing import Dict, Optional
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()

class SocialAuthService:
    def __init__(self):
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.instagram_app_id = os.getenv("INSTAGRAM_APP_ID")
        self.instagram_app_secret = os.getenv("INSTAGRAM_APP_SECRET")
    
    async def exchange_google_code(self, code: str, redirect_uri: str) -> Dict:
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": self.google_client_id,
                "client_secret": self.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
            
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data=token_data
            )
            
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange Google authorization code"
                )
            
            token_json = token_response.json()
            access_token = token_json.get("access_token")
            
            user_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if user_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get Google user info"
                )
            
            user_data = user_response.json()
            return {
                "id": user_data.get("id"),
                "email": user_data.get("email"),
                "name": user_data.get("name"),
                "picture": user_data.get("picture"),
                "provider": "google"
            }
    
    async def exchange_instagram_code(self, code: str, redirect_uri: str) -> Dict:
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": self.instagram_app_id,
                "client_secret": self.instagram_app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": code,
            }
            
            token_response = await client.post(
                "https://api.instagram.com/oauth/access_token",
                data=token_data
            )
            
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange Instagram authorization code"
                )
            
            token_json = token_response.json()
            access_token = token_json.get("access_token")
            user_id = token_json.get("user_id")
            
            user_response = await client.get(
                f"https://graph.instagram.com/{user_id}",
                params={
                    "fields": "id,username,account_type,media_count",
                    "access_token": access_token
                }
            )
            
            if user_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get Instagram user info"
                )
            
            user_data = user_response.json()
            return {
                "id": str(user_data.get("id")),
                "username": user_data.get("username"),
                "account_type": user_data.get("account_type", "PERSONAL"),
                "media_count": user_data.get("media_count", 0),
                "access_token": access_token,
                "provider": "instagram"
            }
    
    async def process_social_login(self, provider: str, code: Optional[str] = None, redirect_uri: Optional[str] = None, user_info: Optional[Dict] = None) -> Dict:
        if provider == "google":
            if user_info:
                # NextAuth에서 이미 처리된 사용자 정보 사용
                return {
                    "id": user_info.get("id"),
                    "email": user_info.get("email"),
                    "name": user_info.get("name"),
                    "picture": user_info.get("picture"),
                    "provider": "google"
                }
            elif code and redirect_uri:
                # Authorization code로 토큰 교환
                return await self.exchange_google_code(code, redirect_uri)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Either user_info or code with redirect_uri is required for Google login"
                )
        elif provider == "instagram":
            if code and redirect_uri:
                return await self.exchange_instagram_code(code, redirect_uri)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Code and redirect_uri are required for Instagram login"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider: {provider}"
            )