#!/usr/bin/env python3
"""
새로 추가된 AI 서비스 모듈 import 테스트
"""

import sys
import os
from pathlib import Path

# 백엔드 경로 추가
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def test_imports():
    """새로 추가된 모듈들의 import 테스트"""
    print("🔍 AI 서비스 모듈 import 테스트 시작...")
    
    try:
        # 기본 패키지들
        print("\n1. 기본 패키지 테스트...")
        import fastapi
        import uvicorn
        import sqlalchemy
        print(f"   ✅ FastAPI {fastapi.__version__}")
        print(f"   ✅ Uvicorn {uvicorn.__version__}")
        print(f"   ✅ SQLAlchemy {sqlalchemy.__version__}")
        
        # 새로 추가된 패키지들
        print("\n2. 새로 추가된 패키지 테스트...")
        try:
            import openai
            print(f"   ✅ OpenAI {openai.__version__}")
        except ImportError:
            print("   ❌ OpenAI 패키지 없음 - pip install openai 필요")
        
        try:
            import websockets
            print(f"   ✅ WebSockets {websockets.__version__}")
        except ImportError:
            print("   ❌ WebSockets 패키지 없음 - pip install websockets 필요")
        
        try:
            import aiofiles
            print(f"   ✅ AioFiles {aiofiles.__version__}")
        except ImportError:
            print("   ❌ AioFiles 패키지 없음 - pip install aiofiles 필요")
        
        # 새로 생성한 서비스 모듈들
        print("\n3. 새로 생성한 서비스 모듈 테스트...")
        try:
            from app.services.openai_service import get_openai_service
            openai_service = get_openai_service()
            print(f"   ✅ OpenAI Service (Mock mode: {openai_service.use_mock})")
        except Exception as e:
            print(f"   ❌ OpenAI Service 모듈 오류: {e}")
        
        try:
            from app.services.comfyui_service import get_comfyui_service
            comfyui_service = get_comfyui_service()
            print(f"   ✅ ComfyUI Service (Mock mode: {comfyui_service.use_mock})")
        except Exception as e:
            print(f"   ❌ ComfyUI Service 모듈 오류: {e}")
        
        try:
            from app.services.content_generation_service import get_content_generation_workflow
            workflow = get_content_generation_workflow()
            print("   ✅ Content Generation Workflow")
        except Exception as e:
            print(f"   ❌ Content Generation Workflow 모듈 오류: {e}")
        
        # 기본 설정 테스트
        print("\n4. 기본 설정 테스트...")
        try:
            from app.core.config import settings
            print(f"   ✅ Settings 로드됨")
            print(f"   📊 DEBUG: {settings.DEBUG}")
            print(f"   📊 DATABASE_URL: {settings.DATABASE_URL[:50]}...")
        except Exception as e:
            print(f"   ❌ Settings 오류: {e}")
        
        print("\n🎉 Import 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"\n❌ Import 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n✅ 모든 모듈이 정상적으로 import되었습니다!")
        print("🚀 이제 백엔드 서버를 실행할 수 있습니다:")
        print("   cd backend && python run.py")
    else:
        print("\n❌ 일부 모듈에 문제가 있습니다. 위의 오류를 해결해주세요.")
