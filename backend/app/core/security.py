from datetime import datetime, timedelta
from typing import Optional, Any, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from typing import Dict
from app.core.config import settings
from app.models.influencer import InfluencerAPI, AIInfluencer
from sqlalchemy.orm import Session
from app.database import get_db

# 로깅 설정
logger = logging.getLogger(__name__)

# 비밀번호 해싱
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT 토큰 스키마
security = HTTPBearer()


# 보안 이벤트 로깅
class SecurityLogger:
    @staticmethod
    def log_dangerous_operation(operation: str, user_id: str, details: dict):
        """위험한 작업 로깅"""
        logger.warning(f"SECURITY ALERT: {operation} by user {user_id} - {details}")

    @staticmethod
    def log_model_deletion(
        model_uuid: str, user_id: str, force_delete: bool, reason: Optional[str] = None
    ):
        """모델 삭제 로깅"""
        logger.warning(
            f"MODEL DELETION: {model_uuid} by {user_id} "
            f"(force_delete={force_delete}, reason={reason or 'No reason provided'})"
        )

    @staticmethod
    def log_unauthorized_access(ip: str, endpoint: str, user_agent: str):
        """무단 접근 로깅"""
        logger.warning(
            f"UNAUTHORIZED ACCESS: {ip} -> {endpoint} (User-Agent: {user_agent})"
        )


def mask_token_for_logging(token: str) -> str:
    """
    로그용 JWT 토큰 마스킹 - 보안 강화
    
    Args:
        token: JWT 토큰 문자열
        
    Returns:
        str: 마스킹된 토큰 (앞 20자 + "...")
    """
    if not token or len(token) <= 20:
        return "[TOKEN_MASKED]"
    
    return f"{token[:20]}..."


# 비밀번호 해싱 함수
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """비밀번호 해싱"""
    return pwd_context.hash(password)


def create_access_token(
    data: dict, expires_delta: Union[timedelta, None] = None
) -> str:
    """액세스 토큰 생성"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow()
    })
    
    # 디버그: SECRET_KEY 확인
    logger.info(f"🔑 Creating token with SECRET_KEY: {settings.SECRET_KEY[:20]}... (algorithm: {settings.ALGORITHM})")
    
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """토큰 검증"""
    try:
        # 토큰 기본 검증
        if not token:
            logger.error(f"❌ JWT verification failed: 토큰이 비어있음")
            return None
        
        if not isinstance(token, str):
            logger.error(f"❌ JWT verification failed: 토큰이 문자열이 아님 (type: {type(token)})")
            return None
        
        # 토큰 구조 확인 (JWT는 3개 부분으로 구성)
        token_parts = token.split('.')
        if len(token_parts) != 3:
            logger.error(f"❌ JWT verification failed: 토큰 구조가 잘못됨 (parts: {len(token_parts)})")
            return None
        
        # 디버그: SECRET_KEY 확인
        logger.info(f"🔐 JWT 토큰 검증 시작:")
        logger.info(f"🔐 - SECRET_KEY: {settings.SECRET_KEY[:20]}... (length: {len(settings.SECRET_KEY)})")
        logger.info(f"🔐 - Algorithm: {settings.ALGORITHM}")
        logger.info(f"🔐 - Token length: {len(token)}")
        logger.info(f"🔐 - Token parts: {len(token_parts)} (header.payload.signature)")
        
        # 서명 없이 페이로드 먼저 확인
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            logger.info(f"🔐 토큰 페이로드 (서명 미검증): {unverified}")
            
            # 만료 시간 확인
            exp = unverified.get('exp')
            iat = unverified.get('iat')
            current_time = datetime.utcnow().timestamp()
            
            if exp:
                exp_datetime = datetime.fromtimestamp(exp)
                logger.info(f"🔐 토큰 만료 시간: {exp_datetime} (현재: {datetime.fromtimestamp(current_time)})")
                if exp < current_time:
                    logger.error(f"❌ JWT verification failed: 토큰이 만료됨 (exp: {exp_datetime})")
                    return None
            
            if iat:
                iat_datetime = datetime.fromtimestamp(iat)
                logger.info(f"🔐 토큰 발행 시간: {iat_datetime}")
                
        except Exception as decode_error:
            logger.error(f"❌ 토큰 페이로드 디코딩 실패: {decode_error}")
            return None
        
        # 실제 서명 검증
        logger.info(f"🔐 서명 검증 시작...")
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        
        logger.info(f"✅ JWT 토큰 검증 성공!")
        logger.info(f"✅ 사용자 ID: {payload.get('sub')}")
        logger.info(f"✅ 이메일: {payload.get('email')}")
        logger.info(f"✅ 그룹: {payload.get('groups', [])}")
        
        return payload
        
    except JWTError as e:
        logger.error(f"❌ JWT verification failed: {type(e).__name__}: {str(e)}")
        logger.error(f"❌ 토큰 정보:")
        logger.error(f"   - Token prefix: {token[:20]}..." if len(token) > 20 else f"   - Token: {token}")
        logger.error(f"   - SECRET_KEY configured: {'Yes' if settings.SECRET_KEY else 'No'}")
        logger.error(f"   - SECRET_KEY prefix: {settings.SECRET_KEY[:20]}..." if settings.SECRET_KEY else "None")
        logger.error(f"   - Algorithm: {settings.ALGORITHM}")
        
        # 구체적인 오류 타입별 메시지
        if "ExpiredSignatureError" in str(type(e)):
            logger.error(f"❌ 토큰 만료 오류")
        elif "InvalidSignatureError" in str(type(e)):
            logger.error(f"❌ 서명 불일치 오류 - SECRET_KEY 확인 필요")
        elif "DecodeError" in str(type(e)):
            logger.error(f"❌ 토큰 디코딩 오류 - 토큰 형식 문제")
        elif "InvalidTokenError" in str(type(e)):
            logger.error(f"❌ 유효하지 않은 토큰")
        
        return None
        
    except Exception as e:
        logger.error(f"❌ JWT verification 예상치 못한 오류: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"❌ 스택 트레이스: {traceback.format_exc()}")
        return None


# 현재 사용자 가져오기 (Enhanced with full payload support)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict:
    """현재 인증된 사용자 정보 반환 (전체 JWT 페이로드 포함)"""
    token = credentials.credentials
    
    # 보안 로깅: 토큰 마스킹 처리 (DEBUG 로그 제거 - 너무 빈번함)
    masked_token = mask_token_for_logging(token)
    # logger.debug(f"🔐 인증 토큰 검증 시작: {masked_token}")
    
    payload = verify_token(token)
    
    if payload is None:
        logger.warning(f"❌ JWT 토큰 검증 실패: {masked_token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 페이로드에서 민감하지 않은 정보만 로깅
    user_info = {
        "user_id": payload.get("sub", "unknown"),
        "provider": payload.get("provider", "unknown"),
        "groups": payload.get("groups", [])
    }
    # logger.debug(f"✅ JWT 토큰 검증 성공: {user_info}")  # DEBUG 로그 제거 - 너무 빈번함

    return payload


# 사용자 ID만 필요한 경우를 위한 함수
async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """현재 인증된 사용자 ID 반환"""
    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


# 보안 검증 함수들
def validate_model_deletion_permission(
    user_id: str, model_uuid: str, force_delete: bool
) -> bool:
    """모델 삭제 권한 검증"""
    # 여기에 실제 권한 검증 로직 구현
    # 예: 관리자만 강제 삭제 가능, 소유자만 일반 삭제 가능 등

    # 임시로 모든 사용자에게 권한 부여 (실제로는 데이터베이스에서 확인)
    return True


def validate_rate_limit(operation: str, user_id: str) -> bool:
    """요청 제한 검증"""
    # 여기에 실제 rate limiting 로직 구현
    # 예: 사용자별 시간당 삭제 횟수 제한

    return True


# 보안 헤더 검증
def validate_security_headers(request: Request) -> bool:
    """보안 헤더 검증"""
    # CSRF 토큰 검증
    # Content-Type 검증
    # 기타 보안 헤더 검증

    return True


# 입력 검증
def sanitize_input(input_str: str) -> str:
    """입력 데이터 정제"""
    # XSS 방지
    # SQL Injection 방지
    # 기타 악성 입력 방지

    if input_str:
        # 기본적인 HTML 태그 제거
        import re

        input_str = re.sub(r"<[^>]+>", "", input_str)
        # 특수 문자 이스케이프
        input_str = input_str.replace("'", "''").replace('"', '""')

    return input_str


# 보안 이벤트 모니터링
class SecurityMonitor:
    def __init__(self):
        self.suspicious_activities = []

    def record_activity(self, activity_type: str, user_id: str, details: dict):
        """보안 활동 기록"""
        activity = {
            "timestamp": datetime.utcnow(),
            "type": activity_type,
            "user_id": user_id,
            "details": details,
        }
        self.suspicious_activities.append(activity)

        # 의심스러운 활동 감지 시 경고
        if self._is_suspicious(activity):
            SecurityLogger.log_dangerous_operation(activity_type, user_id, details)

    def _is_suspicious(self, activity: dict) -> bool:
        """의심스러운 활동 판단"""
        # 예: 짧은 시간 내 많은 삭제 요청
        # 예: 권한이 없는 작업 시도
        # 예: 비정상적인 IP에서의 접근

        return False


# JWT payload generation for social auth
def generate_jwt_payload(user_info: Dict, provider: str) -> Dict:
    """Generate JWT payload with social auth features"""
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
        ],
    }
    
    if provider == "instagram":
        payload["instagram"] = {
            "username": user_info.get("username"),
            "account_type": user_info.get("account_type"),
            "is_business_verified": is_business,
            "business_features": business_features
        }
    
    return payload


# 전역 보안 모니터 인스턴스
security_monitor = SecurityMonitor()

# API 키 인증을 위한 커스텀 의존성
class APIKeyAuth:
    def __init__(self):
        self.scheme = HTTPBearer(auto_error=False)
    
    async def __call__(self, request: Request, db: Session = Depends(get_db)) -> AIInfluencer:
        # Authorization 헤더에서 Bearer 토큰 추출
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Bearer 토큰 형식 확인
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # API 키 추출 (Bearer 제거)
        api_key = authorization[7:]  # "Bearer " 이후의 문자열
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key missing",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        try:
            # API 키로 인플루언서 조회
            influencer_api = (
                db.query(InfluencerAPI)
                .filter(InfluencerAPI.api_value == api_key)
                .first()
            )
            
            if not influencer_api:
                logger.warning(f"❌ 잘못된 API 키 시도: {api_key[:10]}...")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # 인플루언서 정보 조회
            influencer = (
                db.query(AIInfluencer)
                .filter(AIInfluencer.influencer_id == influencer_api.influencer_id)
                .first()
            )
            
            if not influencer:
                logger.error(f"❌ API 키는 유효하지만 인플루언서를 찾을 수 없음: {influencer_api.influencer_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Influencer not found",
                )
            
            # 챗봇 옵션이 활성화된 인플루언서만 접근 가능
            if influencer.chatbot_option is not True:
                logger.warning(f"⚠️ 챗봇이 비활성화된 인플루언서 접근 시도: {influencer.influencer_name}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chatbot is not enabled for this influencer",
                )
            
            # 학습 상태 확인 (사용 가능한 상태여야 함)
            if influencer.learning_status != 1:
                logger.warning(f"⚠️ 학습이 완료되지 않은 인플루언서 접근 시도: {influencer.influencer_name} (status: {influencer.learning_status})")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Influencer is not ready for chat",
                )
            
            logger.info(f"✅ API 키 인증 성공: {influencer.influencer_name}")
            return influencer
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ API 키 인증 중 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

# API 키 인증 의존성 인스턴스
get_current_user_by_api_key = APIKeyAuth()
