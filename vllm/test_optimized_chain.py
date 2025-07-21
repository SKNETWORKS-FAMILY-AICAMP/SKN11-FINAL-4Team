#!/usr/bin/env python3
"""
최적화된 LangChain 체인 성능 테스트
"""

import asyncio
import time
from app.utils.langchain_tone_generator import LangChainToneGenerator
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

async def test_optimized_chain():
    """최적화된 체인 테스트"""
    
    # 테스트 캐릭터
    test_character = {
        "name": "루나",
        "description": "밝고 활발한 20대 여성, 새로운 것을 좋아함",
        "age_range": "20-25세",
        "gender": "FEMALE", 
        "personality": "친근하고 긍정적이며 호기심이 많음",
        "mbti": "ENFP"
    }
    
    # 테스트 질문
    test_question = "오늘 날씨가 정말 좋은데, 뭐 하면서 시간을 보내면 좋을까?"
    
    # API 키 확인
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
        return
    
    # 어투 생성기 초기화
    tone_generator = LangChainToneGenerator(api_key=api_key)
    
    print("🚀 최적화된 LangChain 체인 테스트 시작")
    print(f"📝 캐릭터: {test_character['name']}")
    print(f"❓ 질문: {test_question}")
    print("-" * 50)
    
    try:
        # 최적화된 체인 실행
        start_time = time.time()
        
        responses = await tone_generator.generate_3_tones_parallel(
            character_data=test_character,
            question=test_question
        )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n✅ 완료! 총 소요 시간: {total_time:.2f}초")
        print("-" * 50)
        
        # 결과 출력
        for tone_name, tone_responses in responses.items():
            print(f"\n🎭 {tone_name}:")
            for response in tone_responses:
                print(f"   텍스트: {response['text']}")
                print(f"   해시태그: {response.get('hashtags', 'N/A')}")
                print(f"   설명: {response.get('description', 'N/A')}")
        
        # 성능 분석
        print("\n" + "=" * 50)
        print("📊 성능 분석:")
        print(f"   - 3개 어투 병렬 생성 시간: {total_time:.2f}초")
        print(f"   - 평균 어투당 생성 시간: {total_time/3:.2f}초")
        print(f"   - 예상 순차 처리 시간: {total_time*3:.2f}초")
        print(f"   - 성능 향상: {((total_time*3 - total_time) / (total_time*3) * 100):.1f}%")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

async def compare_chain_versions():
    """체인 버전 간 성능 비교"""
    
    test_character = {
        "name": "알렉스",
        "description": "차분하고 지적인 30대 남성",
        "age_range": "30-35세",
        "gender": "MALE",
        "personality": "논리적이고 분석적이며 신중함",
        "mbti": "INTJ"
    }
    
    questions = [
        "최근에 읽은 책 중에서 추천할 만한 게 있어?",
        "인공지능의 미래에 대해 어떻게 생각해?",
        "스트레스를 해소하는 나만의 방법이 있다면?"
    ]
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
        return
    
    tone_generator = LangChainToneGenerator(api_key=api_key)
    
    print("🔄 체인 성능 비교 테스트")
    print("-" * 50)
    
    total_times = []
    
    for i, question in enumerate(questions, 1):
        print(f"\n📝 테스트 {i}: {question}")
        
        start_time = time.time()
        responses = await tone_generator.generate_3_tones_parallel(
            character_data=test_character,
            question=question
        )
        end_time = time.time()
        
        elapsed = end_time - start_time
        total_times.append(elapsed)
        
        print(f"✅ 완료: {elapsed:.2f}초")
        
        # 첫 번째 응답만 출력
        first_tone = list(responses.keys())[0]
        print(f"   {first_tone}: {responses[first_tone][0]['text'][:100]}...")
    
    # 통계
    avg_time = sum(total_times) / len(total_times)
    print("\n" + "=" * 50)
    print("📊 전체 통계:")
    print(f"   - 평균 생성 시간: {avg_time:.2f}초")
    print(f"   - 최소 시간: {min(total_times):.2f}초")
    print(f"   - 최대 시간: {max(total_times):.2f}초")
    print(f"   - 총 테스트 시간: {sum(total_times):.2f}초")

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 최적화된 LangChain 체인 테스트")
    print("=" * 50)
    
    # 단일 테스트
    asyncio.run(test_optimized_chain())
    
    print("\n" + "=" * 50)
    
    # 성능 비교 테스트
    asyncio.run(compare_chain_versions())