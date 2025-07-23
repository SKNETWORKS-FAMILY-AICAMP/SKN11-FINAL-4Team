#!/usr/bin/env python3
"""
Backend-vLLM 통합 테스트 스크립트
수정된 요청 형식을 테스트합니다.
"""

import asyncio
import sys
import os

# backend 모듈을 import하기 위해 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.vllm_client import VLLMClient, VLLMServerConfig


async def test_generate_qa():
    """generate_qa_for_character 메서드 테스트"""
    
    # 테스트 캐릭터 데이터
    character_data = {
        "name": "테스트 캐릭터",
        "description": "활발하고 긍정적인 20대 여성",
        "age_range": "20-25세",
        "gender": "FEMALE",
        "personality": "친근하고 호기심이 많음",
        "mbti": "ENFP"
    }
    
    # vLLM 클라이언트 설정
    config = VLLMServerConfig(
        base_url="http://localhost:8000",
        timeout=60
    )
    
    print("=" * 50)
    print("🧪 Backend-vLLM 통합 테스트")
    print("=" * 50)
    
    try:
        async with VLLMClient(config) as client:
            print("\n1. vLLM 서버 헬스 체크...")
            is_healthy = await client.health_check()
            print(f"   서버 상태: {'✅ 정상' if is_healthy else '❌ 오류'}")
            
            if not is_healthy:
                print("   ⚠️ vLLM 서버가 실행 중이지 않습니다.")
                return
            
            print("\n2. generate_qa_for_character 테스트...")
            print(f"   캐릭터: {character_data['name']}")
            print("   요청 전송 중...")
            
            # 수정된 메서드 호출
            result = await client.generate_qa_for_character(character_data)
            
            print("\n   ✅ 응답 수신 성공!")
            print(f"   생성된 질문: {result.get('question', 'N/A')[:50]}...")
            
            if 'generation_time_seconds' in result:
                print(f"   생성 시간: {result['generation_time_seconds']:.2f}초")
            
            if 'responses' in result:
                print(f"   생성된 어투 수: {len(result['responses'])}")
                for tone_name, responses in result['responses'].items():
                    if responses:
                        print(f"   - {tone_name}: {responses[0].get('text', 'N/A')[:50]}...")
            
            print("\n✅ 테스트 성공!")
            
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


async def test_direct_api_call():
    """직접 API 호출 테스트 (비교용)"""
    import httpx
    
    print("\n" + "=" * 50)
    print("🔍 직접 API 호출 테스트")
    print("=" * 50)
    
    # 올바른 요청 형식
    payload = {
        "character": {
            "name": "직접 테스트",
            "description": "API 직접 호출 테스트용",
            "age_range": "20-30세",
            "gender": "MALE",
            "personality": "차분하고 지적인",
            "mbti": "INTJ"
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/speech/generate_qa_fast",
                json=payload,
                timeout=60
            )
            
            print(f"응답 상태: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ 직접 호출 성공!")
                print(f"생성 시간: {result.get('generation_time_seconds', 'N/A')}초")
            else:
                print(f"❌ 오류: {response.text}")
                
    except Exception as e:
        print(f"❌ 직접 호출 실패: {e}")


if __name__ == "__main__":
    print("🚀 통합 테스트 시작...\n")
    
    # 비동기 실행
    asyncio.run(test_generate_qa())
    asyncio.run(test_direct_api_call())