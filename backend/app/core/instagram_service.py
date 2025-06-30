import httpx
import os
from typing import Dict, Optional
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()

class InstagramService:
    """AI 인플루언서 모델을 위한 Instagram 연동 서비스"""
    
    def __init__(self):
        self.instagram_app_id = os.getenv("INSTAGRAM_APP_ID")
        self.instagram_app_secret = os.getenv("INSTAGRAM_APP_SECRET")
    
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict:
        """Instagram authorization code를 access token으로 교환"""
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
            
            return {
                "access_token": access_token,
                "user_id": user_id
            }
    
    async def get_instagram_account_info(self, access_token: str, user_id: str) -> Dict:
        """Instagram 계정 정보 조회"""
        async with httpx.AsyncClient() as client:
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
                    detail="Failed to get Instagram account info"
                )
            
            user_data = user_response.json()
            return {
                "instagram_id": str(user_data.get("id")),
                "username": user_data.get("username"),
                "account_type": user_data.get("account_type", "PERSONAL"),
                "media_count": user_data.get("media_count", 0),
                "access_token": access_token,
                "is_business_account": user_data.get("account_type") in ["BUSINESS", "CREATOR"]
            }
    
    async def connect_instagram_account(self, code: str, redirect_uri: str) -> Dict:
        """Instagram 계정 연동 전체 프로세스"""
        # 1. authorization code를 access token으로 교환
        token_data = await self.exchange_code_for_token(code, redirect_uri)
        
        # 2. 계정 정보 조회
        account_info = await self.get_instagram_account_info(
            token_data["access_token"], 
            token_data["user_id"]
        )
        
        return account_info
    
    async def verify_instagram_token(self, access_token: str, instagram_id: str) -> bool:
        """Instagram access token 유효성 검사"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://graph.instagram.com/{instagram_id}",
                    params={
                        "fields": "id",
                        "access_token": access_token
                    }
                )
                return response.status_code == 200
        except:
            return False