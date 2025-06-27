#!/usr/bin/env python3
"""
DDL 기반 마이그레이션 실행 스크립트
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(command, description):
    """명령어 실행 및 결과 출력"""
    print(f"\n🔄 {description}")
    print(f"실행 명령어: {command}")

    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        print(f"✅ {description} 성공")
        if result.stdout:
            print(f"출력: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 실패")
        print(f"오류: {e.stderr}")
        return False


def check_alembic_installed():
    """Alembic이 설치되어 있는지 확인"""
    try:
        subprocess.run(["alembic", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_database_connection():
    """데이터베이스 연결 확인"""
    try:
        from app.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return False


def main():
    """메인 실행 함수"""
    print("🚀 AIMEX DDL 기반 마이그레이션 시작")
    print("=" * 50)

    # 현재 디렉토리를 backend로 변경
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    print(f"📁 작업 디렉토리: {backend_dir}")

    # 1. Alembic 설치 확인
    if not check_alembic_installed():
        print("❌ Alembic이 설치되지 않았습니다.")
        print("다음 명령어로 설치하세요: pip install alembic")
        return False

    # 2. 데이터베이스 연결 확인
    print("\n🔍 데이터베이스 연결 확인 중...")
    if not check_database_connection():
        print("❌ 데이터베이스 연결에 실패했습니다.")
        print("환경 변수와 데이터베이스 설정을 확인하세요.")
        return False

    # 3. 마이그레이션 상태 확인
    if not run_command("alembic current", "현재 마이그레이션 상태 확인"):
        return False

    # 4. 마이그레이션 실행
    if not run_command("alembic upgrade head", "마이그레이션 실행"):
        return False

    # 5. 마이그레이션 후 상태 확인
    if not run_command("alembic current", "마이그레이션 완료 후 상태 확인"):
        return False

    print("\n🎉 DDL 기반 마이그레이션이 성공적으로 완료되었습니다!")
    print("\n📋 다음 단계:")
    print("1. 관리자 그룹 초기화: python init_admin_group.py")
    print("2. 서버 실행: python run.py")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
