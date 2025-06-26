#!/usr/bin/env python3
"""
데이터베이스 마이그레이션 실행 스크립트
"""

import subprocess
import sys
import os


def run_command(command):
    """명령어 실행"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        print(f"✅ {command}")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {command}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False


def main():
    """메인 함수"""
    print("🚀 AIMEX 데이터베이스 마이그레이션 시작")
    print("=" * 50)

    # 현재 디렉토리를 backend로 변경
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # 1. 마이그레이션 초기화 (처음 실행 시)
    if not os.path.exists("alembic/versions"):
        print("📁 Alembic 초기화...")
        if not run_command("alembic init alembic"):
            print("❌ Alembic 초기화 실패")
            sys.exit(1)

    # 2. 기존 마이그레이션 적용 (데이터베이스가 최신 상태가 아닌 경우)
    print("🔄 기존 마이그레이션 적용...")
    if not run_command("alembic upgrade head"):
        print("❌ 기존 마이그레이션 적용 실패")
        sys.exit(1)

    # 3. 마이그레이션 생성 (모델 변경 시)
    print("📝 마이그레이션 생성...")
    if not run_command("alembic revision --autogenerate -m AutoMigration"):
        print("❌ 마이그레이션 생성 실패")
        sys.exit(1)

    # 4. 새 마이그레이션 실행
    print("🔄 새 마이그레이션 실행...")
    if not run_command("alembic upgrade head"):
        print("❌ 새 마이그레이션 실행 실패")
        sys.exit(1)

    print("=" * 50)
    print("✅ 데이터베이스 마이그레이션 완료!")


if __name__ == "__main__":
    main()
