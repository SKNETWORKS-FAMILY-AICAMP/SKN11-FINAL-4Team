from fastapi import APIRouter, HTTPException, status
from .models import SocialLoginRequest, TokenResponse
from .social_auth import SocialAuthService
from .jwt_handler import create_access_token, generate_jwt_payload

auth_router = APIRouter()
social_auth_service = SocialAuthService()

@auth_router.post("/social-login", response_model=TokenResponse)
async def social_login(request: SocialLoginRequest):
    try:
        user_info = await social_auth_service.process_social_login(
            provider=request.provider,
            code=request.code,
            redirect_uri=request.redirect_uri,
            user_info=request.user_info
        )
        
        jwt_payload = generate_jwt_payload(user_info, request.provider)
        access_token = create_access_token(jwt_payload)
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=24 * 60 * 60,  # 24 hours in seconds
            user=jwt_payload
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Social login failed: {str(e)}"
        )

@auth_router.get("/me")
async def get_current_user_info(current_user: dict = None):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return current_user