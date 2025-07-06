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
from app.database import get_db
from app.models.user import User, Team
from app.core.security import get_password_hash


def init_admin_team():
    """관리자 팀 초기화"""
    db: Session = next(get_db())
    
    try:
        # 1. 관리자 팀 생성 (group_id: 0)
        admin_team = db.query(Team).filter(Team.group_id == 0).first()
        
        if not admin_team:
            admin_team = Team(
                group_id=0,
                group_name="관리자 팀",
                group_description="시스템 최고 권한을 가진 관리자 팀",
            )
            db.add(admin_team)
            db.commit()
            print("✅ 관리자 팀이 생성되었습니다.")
        else:
            print("ℹ️ 관리자 팀이 이미 존재합니다.")

        # 2. 관리자 사용자 생성 (이메일: admin@aimex.com)
        admin_user = db.query(User).filter(User.email == "admin@aimex.com").first()
        
        if not admin_user:
            admin_user = User(
                provider_id="admin",
                provider="email",
                user_name="관리자",
                email="admin@aimex.com",
            )
            db.add(admin_user)
            db.commit()
            print("✅ 관리자 사용자가 생성되었습니다.")
        else:
            print("ℹ️ 관리자 사용자가 이미 존재합니다.")

        # 3. 관리자 사용자를 관리자 팀에 추가
        if admin_user not in admin_team.users:
            admin_team.users.append(admin_user)
            db.commit()
            print("✅ 관리자 사용자가 관리자 팀에 추가되었습니다.")
        else:
            print("ℹ️ 관리자 사용자가 이미 관리자 팀에 속해 있습니다.")

        print("\n🎉 관리자 팀 초기화가 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()


def check_admin_team_status():
    """관리자 팀 상태 확인"""
    db: Session = next(get_db())
    
    try:
        # 관리자 팀 확인
        admin_team = db.query(Team).filter(Team.group_id == 0).first()
        admin_user = db.query(User).filter(User.email == "admin@aimex.com").first()
        
        print("📊 관리자 팀 상태 확인:")
        print(f"관리자 팀(0번): {'✅ 존재' if admin_team else '❌ 없음'}")
        print(f"관리자 사용자: {'✅ 존재' if admin_user else '❌ 없음'}")
        
        if admin_team and admin_user:
            is_admin_in_team = admin_user in admin_team.users
            print(
                f"관리자 팀 멤버십: {'✅ 확인' if is_admin_in_team else '❌ 없음'}"
            )
        
        print(f"총 팀 수: {db.query(Team).count()}")
        print(f"총 사용자 수: {db.query(User).count()}")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 관리자 팀 초기화를 시작합니다...")
    init_admin_team()
    print("\n" + "="*50)
    check_admin_team_status()
