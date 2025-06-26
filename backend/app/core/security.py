from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from app.core.config import settings

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


# 비밀번호 해싱 함수
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """비밀번호 해싱"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """액세스 토큰 생성"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """토큰 검증"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


# 현재 사용자 가져오기
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
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


# 전역 보안 모니터 인스턴스
security_monitor = SecurityMonitor()
