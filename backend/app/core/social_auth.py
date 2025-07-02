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
        self.naver_client_id = os.getenv("NAVER_CLIENT_ID")
        self.naver_client_secret = os.getenv("NAVER_CLIENT_SECRET")
        self.instagram_app_id = os.getenv("INSTAGRAM_APP_ID")
        self.instagram_app_secret = os.getenv("INSTAGRAM_APP_SECRET")
    
    async def exchange_google_code(self, code: str, redirect_uri: str) -> Dict:
        """Google OAuth2 authorization code를 사용자 정보로 교환"""
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
    
    async def exchange_naver_code(self, code: str, redirect_uri: str) -> Dict:
        """Naver OAuth2 authorization code를 사용자 정보로 교환"""
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": self.naver_client_id,
                "client_secret": self.naver_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            }
            
            token_response = await client.post(
                "https://nid.naver.com/oauth2.0/token",
                data=token_data
            )
            
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange Naver authorization code"
                )
            
            token_json = token_response.json()
            access_token = token_json.get("access_token")
            
            user_response = await client.get(
                "https://openapi.naver.com/v1/nid/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if user_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get Naver user info"
                )
            
            user_data = user_response.json()
            response_data = user_data.get("response", {})
            return {
                "id": response_data.get("id"),
                "email": response_data.get("email"),
                "name": response_data.get("name"),
                "picture": response_data.get("profile_image"),
                "provider": "naver"
            }
    
    async def exchange_instagram_business_code(self, code: str, redirect_uri: str) -> Dict:
        """Instagram API with Instagram Login OAuth2 authorization code를 사용자 정보로 교환"""
        async with httpx.AsyncClient() as client:
            # Step 1: 단기 액세스 토큰 획득
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
            short_lived_token = token_json.get("access_token")
            user_id = token_json.get("user_id")
            
            # Step 2: 장기 액세스 토큰으로 교환 (60일 유효)
            long_lived_response = await client.get(
                "https://graph.instagram.com/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": self.instagram_app_secret,
                    "access_token": short_lived_token
                }
            )
            
            access_token = short_lived_token  # 기본값
            expires_in = 3600  # 1시간
            
            if long_lived_response.status_code == 200:
                long_lived_json = long_lived_response.json()
                access_token = long_lived_json.get("access_token", short_lived_token)
                expires_in = long_lived_json.get("expires_in", 5184000)  # 60일
            
            # Step 3: Instagram API with Instagram Login으로 사용자 정보 조회
            user_response = await client.get(
                f"https://graph.instagram.com/v21.0/{user_id}",
                params={
                    "fields": "id,username,account_type,name,biography,followers_count,follows_count,media_count,profile_picture_url,website",
                    "access_token": access_token
                }
            )
            
            if user_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get Instagram user info"
                )
            
            user_data = user_response.json()
            account_type = user_data.get("account_type", "PERSONAL")
            
            # Step 4: 비즈니스 계정인 경우 추가 인사이트 정보 조회
            business_insights = {}
            if account_type in ["BUSINESS", "CREATOR"]:
                try:
                    # 계정 인사이트 조회 (지난 7일)
                    insights_response = await client.get(
                        f"https://graph.instagram.com/v21.0/{user_id}/insights",
                        params={
                            "metric": "impressions,reach,profile_views",
                            "period": "day",
                            "since": "2024-01-01",
                            "until": "2024-01-07",
                            "access_token": access_token
                        }
                    )
                    
                    if insights_response.status_code == 200:
                        business_insights = insights_response.json()
                except Exception:
                    # 인사이트 조회 실패 시 무시
                    pass
            
            return {
                "id": str(user_data.get("id")),
                "access_token": access_token,
                "expires_in": expires_in,
                "provider": "instagram_api_login"
            }
    
    async def get_instagram_user_info(self, instagram_id: str, access_token: str) -> Dict:
        """Instagram API로 사용자 정보 실시간 조회"""
        async with httpx.AsyncClient() as client:
            try:
                user_response = await client.get(
                    f"https://graph.instagram.com/v21.0/{instagram_id}",
                    params={
                        "fields": "id,username,account_type,name,biography,followers_count,follows_count,media_count,profile_picture_url,website",
                        "access_token": access_token
                    }
                )
                
                if user_response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to get Instagram user info"
                    )
                
                return user_response.json()
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Instagram API error: {str(e)}"
                )
    
    async def process_social_login(self, provider: str, code: Optional[str] = None, redirect_uri: Optional[str] = None, user_info: Optional[Dict] = None) -> Dict:
        """소셜 로그인 처리 (Google, Naver 지원)"""
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
        elif provider == "naver":
            if user_info:
                # 프론트에서 이미 처리된 사용자 정보 사용
                return {
                    "id": user_info.get("id"),
                    "email": user_info.get("email"),
                    "name": user_info.get("name"),
                    "picture": user_info.get("picture"),
                    "provider": "naver"
                }
            elif code and redirect_uri:
                # Authorization code로 토큰 교환
                return await self.exchange_naver_code(code, redirect_uri)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Either user_info or code with redirect_uri is required for Naver login"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider: {provider}. Only 'google' and 'naver' are supported for social login."
            )