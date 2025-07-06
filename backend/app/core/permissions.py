"""
권한 검증 관련 공통 유틸리티
Admin 권한 체크, 그룹 권한 체크 등 권한 관련 로직 통합
"""

import logging
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Union, Dict, Any

from app.models.user import User

logger = logging.getLogger(__name__)

# 시스템 설정: Admin 그룹 ID (표준화)
ADMIN_GROUP_ID = 1  # 0에서 1로 표준화


def check_admin_permission(user: Union[User, Dict[str, Any]], db: Session = None) -> bool:
    """
    통합된 Admin 권한 체크 함수
    Args:
        user: User 객체 또는 사용자 딕셔너리
        db: 데이터베이스 세션 (필요한 경우)
    Returns:
        bool: Admin 권한 여부
    Raises:
        HTTPException: Admin 권한이 없는 경우
    """
    try:
        # User 객체인 경우
        if isinstance(user, User):
            user_group_id = user.group_id
            user_id = user.user_id
        # 딕셔너리인 경우  
        elif isinstance(user, dict):
            user_group_id = user.get('group_id')
            user_id = user.get('user_id', 'unknown')
        else:
            logger.error(f"지원하지 않는 사용자 타입: {type(user)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="잘못된 사용자 정보 형식"
            )
        
        # Admin 권한 확인
        if user_group_id != ADMIN_GROUP_ID:
            logger.warning(f"Admin 권한 없음: user_id={user_id}, group_id={user_group_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="관리자 권한이 필요합니다."
            )
        
        logger.info(f"Admin 권한 확인 성공: user_id={user_id}")
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin 권한 체크 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="권한 확인 중 오류가 발생했습니다."
        )


def check_user_group_permission(user: Union[User, Dict[str, Any]], required_group_id: int, 
                               allow_admin: bool = True, db: Session = None) -> bool:
    """
    특정 그룹 권한 체크 함수
    Args:
        user: User 객체 또는 사용자 딕셔너리
        required_group_id: 필요한 그룹 ID
        allow_admin: Admin 권한도 허용할지 여부 (기본: True)
        db: 데이터베이스 세션 (필요한 경우)
    Returns:
        bool: 권한 여부
    Raises:
        HTTPException: 권한이 없는 경우
    """
    try:
        # User 객체인 경우
        if isinstance(user, User):
            user_group_id = user.group_id
            user_id = user.user_id
        # 딕셔너리인 경우
        elif isinstance(user, dict):
            user_group_id = user.get('group_id')
            user_id = user.get('user_id', 'unknown')
        else:
            logger.error(f"지원하지 않는 사용자 타입: {type(user)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="잘못된 사용자 정보 형식"
            )
        
        # Admin 권한 체크 (허용되는 경우)
        if allow_admin and user_group_id == ADMIN_GROUP_ID:
            logger.info(f"Admin 권한으로 접근 허용: user_id={user_id}")
            return True
        
        # 특정 그룹 권한 체크
        if user_group_id == required_group_id:
            logger.info(f"그룹 권한 확인 성공: user_id={user_id}, group_id={required_group_id}")
            return True
        
        # 권한 없음
        logger.warning(f"그룹 권한 없음: user_id={user_id}, user_group={user_group_id}, required_group={required_group_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"그룹 {required_group_id} 권한이 필요합니다."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"그룹 권한 체크 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="권한 확인 중 오류가 발생했습니다."
        )


def check_resource_ownership(user: Union[User, Dict[str, Any]], resource_user_id: str, 
                           allow_admin: bool = True) -> bool:
    """
    리소스 소유권 체크 함수
    Args:
        user: User 객체 또는 사용자 딕셔너리
        resource_user_id: 리소스의 소유자 ID
        allow_admin: Admin 권한도 허용할지 여부 (기본: True)
    Returns:
        bool: 소유권 여부
    Raises:
        HTTPException: 소유권이 없는 경우
    """
    try:
        # User 객체인 경우
        if isinstance(user, User):
            user_id = user.user_id
            user_group_id = user.group_id
        # 딕셔너리인 경우
        elif isinstance(user, dict):
            user_id = user.get('user_id')
            user_group_id = user.get('group_id')
        else:
            logger.error(f"지원하지 않는 사용자 타입: {type(user)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="잘못된 사용자 정보 형식"
            )
        
        # Admin 권한 체크 (허용되는 경우)
        if allow_admin and user_group_id == ADMIN_GROUP_ID:
            logger.info(f"Admin 권한으로 리소스 접근 허용: user_id={user_id}, resource_owner={resource_user_id}")
            return True
        
        # 소유권 체크
        if user_id == resource_user_id:
            logger.info(f"리소스 소유권 확인 성공: user_id={user_id}")
            return True
        
        # 소유권 없음
        logger.warning(f"리소스 소유권 없음: user_id={user_id}, resource_owner={resource_user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 리소스에 대한 권한이 없습니다."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리소스 소유권 체크 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="권한 확인 중 오류가 발생했습니다."
        )


def get_user_accessible_group_ids(user: Union[User, Dict[str, Any]]) -> list[int]:
    """
    사용자가 접근 가능한 그룹 ID 목록 반환
    Args:
        user: User 객체 또는 사용자 딕셔너리
    Returns:
        list[int]: 접근 가능한 그룹 ID 목록
    """
    try:
        # User 객체인 경우
        if isinstance(user, User):
            user_group_id = user.group_id
        # 딕셔너리인 경우
        elif isinstance(user, dict):
            user_group_id = user.get('group_id')
        else:
            logger.error(f"지원하지 않는 사용자 타입: {type(user)}")
            return []
        
        # Admin은 모든 그룹에 접근 가능 (추후 확장성을 위해 현재는 자신의 그룹만)
        if user_group_id == ADMIN_GROUP_ID:
            # TODO: Admin이 접근 가능한 모든 그룹 ID를 반환하도록 확장
            return [user_group_id]
        
        # 일반 사용자는 자신의 그룹만 접근 가능
        return [user_group_id] if user_group_id is not None else []
        
    except Exception as e:
        logger.error(f"접근 가능한 그룹 ID 조회 중 오류: {e}")
        return []


def is_admin(user: Union[User, Dict[str, Any]]) -> bool:
    """
    사용자가 Admin인지 간단히 확인하는 함수 (예외 발생 안함)
    Args:
        user: User 객체 또는 사용자 딕셔너리
    Returns:
        bool: Admin 여부
    """
    try:
        # User 객체인 경우
        if isinstance(user, User):
            return user.group_id == ADMIN_GROUP_ID
        # 딕셔너리인 경우
        elif isinstance(user, dict):
            return user.get('group_id') == ADMIN_GROUP_ID
        else:
            return False
    except Exception:
        return False