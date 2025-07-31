#!/usr/bin/env python3
"""
vLLM Generation Worker 스트리밍 테스트
"""
import asyncio
import json
import os
import sys

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generation_worker import stream_handler, initialize_engine, initialize_async_engine


async def test_streaming():
    """스트리밍 기능 테스트"""
    print("🧪 vLLM 스트리밍 테스트 시작")
    
    # 테스트 페이로드
    test_job = {
        "input": {
            "hf_token": os.environ.get("HF_TOKEN", "test_token"),
            "hf_repo": "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct",  # 베이스 모델로 테스트
            "system_message": "당신은 도움이 되는 AI 어시스턴트입니다.",
            "prompt": "간단한 파이썬 함수를 작성해주세요.",
            "temperature": 0.7,
            "max_tokens": 100,
            "top_p": 0.9,
            "top_k": 50,
            "repetition_penalty": 1.1
        }
    }
    
    try:
        print("📝 테스트 페이로드:")
        print(json.dumps(test_job["input"], indent=2, ensure_ascii=False))
        print("\n" + "="*50)
        
        # 스트리밍 테스트
        print("🌊 스트리밍 시작...")
        chunk_count = 0
        total_text = ""
        
        async for chunk_data in stream_handler(test_job):
            chunk_count += 1
            
            if isinstance(chunk_data, dict):
                if "error" in chunk_data:
                    print(f"❌ 에러 발생: {chunk_data['error']}")
                    break
                
                chunk = chunk_data.get("chunk", "")
                is_final = chunk_data.get("is_final", False)
                generated_text = chunk_data.get("generated_text", "")
                
                print(f"📦 청크 #{chunk_count}: '{chunk}' (final: {is_final})")
                total_text += chunk
                
                if is_final:
                    print(f"\n✅ 스트리밍 완료!")
                    print(f"📊 총 청크 수: {chunk_count}")
                    print(f"📝 전체 텍스트 길이: {len(total_text)} chars")
                    print(f"📄 생성된 텍스트:\n{'-'*30}")
                    print(generated_text)
                    print("-"*30)
                    break
            else:
                print(f"⚠️ 예상치 못한 데이터 형식: {type(chunk_data)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sync_streaming():
    """동기 방식 스트리밍 테스트"""
    print("🔧 동기 엔진 초기화 테스트...")
    
    try:
        # 동기 엔진 초기화
        initialize_engine()
        print("✅ 동기 엔진 초기화 성공")
        return True
    except Exception as e:
        print(f"❌ 동기 엔진 초기화 실패: {e}")
        return False


async def test_async_streaming():
    """비동기 방식 스트리밍 테스트"""
    print("🔧 비동기 엔진 초기화 테스트...")
    
    try:
        # 비동기 엔진 초기화
        await initialize_async_engine()
        print("✅ 비동기 엔진 초기화 성공")
        return True
    except Exception as e:
        print(f"❌ 비동기 엔진 초기화 실패: {e}")
        return False


async def main():
    """메인 테스트 함수"""
    print("🚀 vLLM Generation Worker 스트리밍 테스트")
    print("="*60)
    
    # 환경 변수 확인
    streaming_enabled = os.environ.get("ENABLE_STREAMING", "true").lower() == "true"
    print(f"📊 ENABLE_STREAMING: {streaming_enabled}")
    print(f"📊 HF_TOKEN 설정됨: {'예' if os.environ.get('HF_TOKEN') else '아니오'}")
    print()
    
    # 1. 동기 엔진 테스트
    print("1️⃣ 동기 엔진 테스트")
    if test_sync_streaming():
        print("✅ 동기 엔진 테스트 통과\n")
    else:
        print("❌ 동기 엔진 테스트 실패\n")
    
    # 2. 비동기 엔진 테스트 (선택적)
    print("2️⃣ 비동기 엔진 테스트")
    if await test_async_streaming():
        print("✅ 비동기 엔진 테스트 통과\n")
    else:
        print("❌ 비동기 엔진 테스트 실패 (AsyncLLMEngine 미지원 가능)\n")
    
    # 3. 스트리밍 테스트
    print("3️⃣ 실제 스트리밍 테스트")
    if await test_streaming():
        print("✅ 전체 테스트 성공!")
        return True
    else:
        print("❌ 스트리밍 테스트 실패!")
        return False


if __name__ == "__main__":
    # 환경 변수 설정 (테스트용)
    os.environ.setdefault("ENABLE_STREAMING", "true")
    os.environ.setdefault("PRELOAD_MODEL", "false")
    
    # 비동기 테스트 실행
    success = asyncio.run(main())
    sys.exit(0 if success else 1)