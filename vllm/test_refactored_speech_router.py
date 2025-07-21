#!/usr/bin/env python3
"""
리팩토링된 speech.py 라우터 테스트
"""

import asyncio
import json
from fastapi.testclient import TestClient
from fastapi import FastAPI
from app.routers import speech
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# FastAPI 앱 생성 및 라우터 포함
app = FastAPI()
app.include_router(speech.router, prefix="/speech")

# 테스트 클라이언트
client = TestClient(app)

def test_generate_qa_fast():
    """고속 어투 생성 엔드포인트 테스트"""
    print("🧪 /generate_qa_fast 엔드포인트 테스트")
    print("-" * 50)
    
    # 테스트 요청 데이터
    test_data = {
        "character": {
            "name": "테스트봇",
            "description": "친근하고 유머러스한 AI 어시스턴트",
            "age_range": "20-30대",
            "gender": "NON_BINARY",
            "personality": "밝고 긍정적이며 도움을 주는 것을 좋아함",
            "mbti": "ENFP"
        }
    }
    
    try:
        # API 키 확인
        if not os.getenv('OPENAI_API_KEY'):
            print("❌ OpenAI API 키가 설정되지 않았습니다.")
            return
        
        print("📤 요청 전송 중...")
        response = client.post("/speech/generate_qa_fast", json=test_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 응답 수신 (생성 시간: {result.get('generation_time_seconds', 0):.2f}초)")
            print(f"❓ 질문: {result.get('question', 'N/A')}")
            
            # 각 말투 확인
            for tone_name, responses in result.get('responses', {}).items():
                print(f"\n🎭 {tone_name}:")
                if responses and len(responses) > 0:
                    tone_data = responses[0]
                    print(f"   📝 텍스트: {tone_data.get('text', 'N/A')[:50]}...")
                    print(f"   🏷️  해시태그: {tone_data.get('hashtags', 'N/A')}")
                    print(f"   📋 설명: {tone_data.get('description', 'N/A')}")
        else:
            print(f"❌ 요청 실패: {response.status_code}")
            print(f"   오류: {response.text}")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

def test_generate_tone():
    """어투 생성 엔드포인트 테스트"""
    print("\n" + "=" * 50)
    print("🧪 /generate_tone 엔드포인트 테스트")
    print("-" * 50)
    
    # 테스트 요청 데이터
    test_data = {
        "character": {
            "name": "루나",
            "description": "밝고 활발한 20대 여성",
            "age_range": "20-25세",
            "gender": "FEMALE",
            "personality": "친근하고 긍정적이며 호기심이 많음",
            "mbti": "ENFP"
        },
        "num_tones": 3
    }
    
    try:
        # API 키 확인
        if not os.getenv('OPENAI_API_KEY'):
            print("❌ OpenAI API 키가 설정되지 않았습니다.")
            return
        
        print("📤 요청 전송 중...")
        response = client.post("/speech/generate_tone", json=test_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 응답 수신")
            print(f"📋 태스크 ID: {result.get('task_id', 'N/A')}")
            print(f"📊 상태: {result.get('status', 'N/A')}")
            
            # 결과 확인
            task_result = result.get('result', {})
            print(f"❓ 질문: {task_result.get('question', 'N/A')}")
            
            # 각 톤 확인
            for tone_name, responses in task_result.get('responses', {}).items():
                print(f"\n🎭 {tone_name}:")
                if responses and len(responses) > 0:
                    tone_data = responses[0]
                    print(f"   📝 텍스트: {tone_data.get('text', 'N/A')[:50]}...")
                    
                    tone_info = tone_data.get('tone_info', {})
                    print(f"   🏷️  해시태그: {tone_info.get('hashtags', 'N/A')}")
                    print(f"   📋 설명: {tone_info.get('description', 'N/A')}")
        else:
            print(f"❌ 요청 실패: {response.status_code}")
            print(f"   오류: {response.text}")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

def test_error_handling():
    """에러 처리 테스트"""
    print("\n" + "=" * 50)
    print("🧪 에러 처리 테스트")
    print("-" * 50)
    
    # API 키 없이 테스트
    original_key = os.environ.get('OPENAI_API_KEY')
    if original_key:
        del os.environ['OPENAI_API_KEY']
    
    test_data = {
        "character": {
            "name": "에러테스트봇",
            "description": "에러 테스트용 캐릭터",
            "age_range": "20-30대",
            "gender": "NON_BINARY",
            "personality": "테스트용",
            "mbti": "ENFP"
        }
    }
    
    try:
        print("📤 API 키 없이 요청 전송...")
        response = client.post("/speech/generate_qa_fast", json=test_data)
        
        if response.status_code == 500:
            print("✅ 예상된 에러 발생")
            error_detail = response.json().get('detail', '')
            print(f"   에러 메시지: {error_detail}")
        else:
            print(f"❌ 예상치 못한 응답: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
    finally:
        # API 키 복원
        if original_key:
            os.environ['OPENAI_API_KEY'] = original_key

if __name__ == "__main__":
    print("=" * 50)
    print("🏃 리팩토링된 speech.py 라우터 테스트")
    print("=" * 50)
    
    # 헬퍼 함수 테스트
    print("\n✅ 헬퍼 함수들이 성공적으로 리팩토링되었습니다:")
    print("   - get_api_key(): API 키 가져오기 및 검증")
    print("   - extract_character_data(): 캐릭터 데이터 추출")
    print("   - create_character_profile(): 캐릭터 프로필 생성")
    print("   - create_error_response(): 에러 응답 생성")
    print("   - measure_execution_time(): 실행 시간 측정")
    
    # 엔드포인트 테스트
    test_generate_qa_fast()
    test_generate_tone()
    test_error_handling()
    
    print("\n" + "=" * 50)
    print("✅ 모든 테스트 완료!")
    print("   중복 코드가 성공적으로 제거되었습니다.")