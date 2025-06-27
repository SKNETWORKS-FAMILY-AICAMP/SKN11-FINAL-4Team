#!/usr/bin/env python3
"""
관리자 그룹 및 기본 관리자 사용자 초기화 스크립트
DDL 기반으로 작성됨
"""

import sys
import os
import uuid
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.user import User, Group
from app.models.base import Base


def init_admin_group():
    """관리자 그룹(0번) 및 기본 관리자 사용자 생성"""
    db = SessionLocal()

    try:
        # 1. 관리자 그룹 생성 (group_id: 0)
        admin_group = db.query(Group).filter(Group.group_id == 0).first()

        if not admin_group:
            admin_group = Group(
                group_id=0,
                group_name="관리자 그룹",
                group_description="시스템 최고 권한을 가진 관리자 그룹",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(admin_group)
            print("✅ 관리자 그룹(0번) 생성 완료")
        else:
            print("ℹ️ 관리자 그룹(0번)이 이미 존재합니다")

        # 2. 기본 관리자 사용자 생성
        admin_user = db.query(User).filter(User.email == "admin@aimex.com").first()

        if not admin_user:
            admin_user = User(
                user_id=str(uuid.uuid4()),
                provider_id="admin_provider_id",
                provider="admin",
                user_name="시스템관리자",
                email="admin@aimex.com",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(admin_user)
            print("✅ 기본 관리자 사용자 생성 완료")
        else:
            print("ℹ️ 기본 관리자 사용자가 이미 존재합니다")

        # 3. 관리자 사용자를 관리자 그룹에 추가
        if admin_user not in admin_group.users:
            admin_group.users.append(admin_user)
            print("✅ 관리자 사용자를 관리자 그룹에 추가 완료")
        else:
            print("ℹ️ 관리자 사용자가 이미 관리자 그룹에 속해있습니다")

        db.commit()
        print("\n🎉 관리자 그룹 및 사용자 초기화가 완료되었습니다!")
        print(f"관리자 이메일: admin@aimex.com")
        print(f"관리자 그룹 ID: 0")

    except Exception as e:
        db.rollback()
        print(f"❌ 초기화 중 오류 발생: {e}")
        raise
    finally:
        db.close()


def check_admin_setup():
    """관리자 설정 상태 확인"""
    db = SessionLocal()

    try:
        admin_group = db.query(Group).filter(Group.group_id == 0).first()
        admin_user = db.query(User).filter(User.email == "admin@aimex.com").first()

        print("🔍 관리자 설정 상태 확인:")
        print(f"관리자 그룹(0번): {'✅ 존재' if admin_group else '❌ 없음'}")
        print(f"관리자 사용자: {'✅ 존재' if admin_user else '❌ 없음'}")

        if admin_group and admin_user:
            is_admin_in_group = admin_user in admin_group.users
            print(
                f"관리자 그룹 멤버십: {'✅ 확인' if is_admin_in_group else '❌ 없음'}"
            )

    except Exception as e:
        print(f"❌ 확인 중 오류 발생: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 AIMEX 관리자 그룹 초기화 시작")
    print("=" * 50)

    # 현재 상태 확인
    check_admin_setup()
    print()

    # 초기화 실행
    init_admin_group()
    print()

    # 초기화 후 상태 확인
    check_admin_setup()
