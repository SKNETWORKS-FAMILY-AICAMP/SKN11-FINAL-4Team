#!/usr/bin/env python3
"""
LangChain 기반 어투 생성 성능 테스트 스크립트
"""

import asyncio
import time
import os
from app.utils.langchain_tone_generator import LangChainToneGenerator

async def test_langchain_tone_performance():
    """LangChain 어투 생성 성능 테스트"""
    
    # OpenAI API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        return
    
    # 테스트 캐릭터 데이터
    character_data = {
        "name": "AI 어시스턴트 민지",
        "description": "밝고 친근한 AI 어시스턴트",
        "personality": "밝고 친근하며 호기심이 많은 성격",
        "age_range": "20대",
        "gender": "여성",
        "mbti": "ENFP"
    }
    
    # 테스트 질문
    question = "오늘 하루는 어떻게 보내셨나요?"
    
    print("🚀 LangChain 어투 생성 성능 테스트 시작")
    print(f"📝 캐릭터: {character_data['name']}")
    print(f"❓ 질문: {question}")
    
    # LangChain 어투 생성기 생성
    tone_generator = LangChainToneGenerator(api_key=api_key)
    
    # 성능 테스트 (5회 반복)
    total_times = []
    
    for i in range(5):
        print(f"\n🔄 테스트 {i+1}/5")
        
        # 성능 측정
        start_time = time.time()
        
        try:
            responses = await tone_generator.generate_3_tones_parallel(
                character_data=character_data,
                question=question
            )
            
            end_time = time.time()
            generation_time = end_time - start_time
            total_times.append(generation_time)
            
            print(f"✅ 생성 완료: 3개 어투")
            print(f"⏱️ 소요시간: {generation_time:.2f}초")
            
            # 첫 번째 테스트에서만 샘플 출력
            if i == 0:
                print(f"\n📝 샘플 어투들:")
                for tone_name, tone_list in responses.items():
                    if tone_list:
                        tone_data = tone_list[0]
                        print(f"   {tone_name}: {tone_data['text'][:100]}...")
                        print(f"   설명: {tone_data['tone_info']['description']}")
                        print(f"   해시태그: {tone_data['tone_info']['hashtags']}")
                        print()
                
        except Exception as e:
            print(f"❌ 테스트 실패: {e}")
            return
    
    # 성능 요약
    avg_time = sum(total_times) / len(total_times)
    min_time = min(total_times)
    max_time = max(total_times)
    
    print(f"\n📊 성능 요약 (5회 테스트):")
    print(f"   평균 시간: {avg_time:.2f}초")
    print(f"   최소 시간: {min_time:.2f}초")
    print(f"   최대 시간: {max_time:.2f}초")
    
    # 기존 순차 처리와 비교 (추정)
    estimated_sequential_time = avg_time * 3  # 순차 처리 추정치
    improvement = estimated_sequential_time / avg_time
    
    print(f"\n🚀 예상 성능 개선:")
    print(f"   기존 순차 처리 (추정): {estimated_sequential_time:.2f}초")
    print(f"   LangChain 병렬 처리: {avg_time:.2f}초")
    print(f"   성능 개선 배수: {improvement:.1f}배")
    
    print("\n✅ 어투 생성 성능 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(test_langchain_tone_performance())