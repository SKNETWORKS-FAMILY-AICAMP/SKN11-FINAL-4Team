#!/usr/bin/env python3
"""
파일 업로드 테스트 스크립트
"""

import os
import sys
from pathlib import Path

# 업로드 디렉토리 확인
upload_dir = Path("uploads")
backend_dir = Path("C:/encore-skn11/SKN/SKN-FINAL/backend")
frontend_dir = Path("C:/encore-skn11/SKN/SKN-FINAL/frontend")

print("🔍 AIMEX 이미지 업로드 환경 체크")
print("=" * 50)

# 1. 백엔드 업로드 디렉토리 확인
backend_upload_dir = backend_dir / "uploads"
if backend_upload_dir.exists():
    print(f"✅ 백엔드 업로드 디렉토리 존재: {backend_upload_dir}")
else:
    print(f"❌ 백엔드 업로드 디렉토리 없음: {backend_upload_dir}")
    backend_upload_dir.mkdir(exist_ok=True)
    print(f"🔧 업로드 디렉토리 생성: {backend_upload_dir}")

# 2. 디렉토리 권한 확인
try:
    test_file = backend_upload_dir / "test.txt"
    test_file.write_text("test")
    test_file.unlink()
    print("✅ 업로드 디렉토리 쓰기 권한 확인")
except Exception as e:
    print(f"❌ 업로드 디렉토리 쓰기 권한 없음: {e}")

# 3. 프론트엔드 환경변수 확인
frontend_env = frontend_dir / ".env.local"
if frontend_env.exists():
    print(f"✅ 프론트엔드 환경변수 파일 존재: {frontend_env}")
    with open(frontend_env, 'r', encoding='utf-8') as f:
        content = f.read()
        if "NEXT_PUBLIC_BACKEND_URL" in content:
            print("✅ NEXT_PUBLIC_BACKEND_URL 설정 확인")
        else:
            print("❌ NEXT_PUBLIC_BACKEND_URL 설정 없음")
else:
    print(f"❌ 프론트엔드 환경변수 파일 없음: {frontend_env}")

# 4. 백엔드 환경변수 확인
backend_env = backend_dir / ".env"
if backend_env.exists():
    print(f"✅ 백엔드 환경변수 파일 존재: {backend_env}")
else:
    print(f"❌ 백엔드 환경변수 파일 없음: {backend_env}")

print("\n🎯 이미지 업로드 기능 테스트 가이드")
print("=" * 50)
print("1. 백엔드 서버 실행: python run.py")
print("2. 프론트엔드 서버 실행: npm run dev")
print("3. 브라우저에서 /create-post 접속")
print("4. 이미지 업로드 버튼 클릭하여 테스트")
print("5. AI 이미지 생성 버튼 클릭하여 테스트")
print("\n📋 확인사항:")
print("- 업로드된 이미지가 미리보기에 표시되는지")
print("- 생성된 이미지가 올바르게 로드되는지")
print("- 이미지 삭제 기능이 작동하는지")
print("- 게시글 저장 시 이미지가 포함되는지")
