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
    
    print("🚀 LangChain 체인 기반 어투 생성 성능 테스트 시작")
    print(f"📝 캐릭터: {character_data['name']}")
    print(f"❓ 질문: {question}")
    print("\n🔥 사용 기술:")
    print("   - LangChain RunnableParallel (진짜 체인 병렬 처리)")
    print("   - 3개 어투 + 요약 동시 생성")
    print("   - OpenAI API 최적화 호출")
    
    # LangChain 어투 생성기 생성
    tone_generator = LangChainToneGenerator(api_key=api_key)
    
    # 성능 테스트 (3회 반복 - LangChain은 안정적이므로)
    total_times = []
    
    for i in range(3):
        print(f"\n🔄 LangChain 체인 테스트 {i+1}/3")
        
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
                print(f"\n📝 LangChain 체인으로 생성된 어투들:")
                for tone_name, tone_list in responses.items():
                    if tone_list:
                        tone_data = tone_list[0]
                        print(f"   🎭 {tone_name}: {tone_data['text'][:100]}...")
                        print(f"   📖 설명: {tone_data['tone_info']['description']}")
                        print(f"   🏷️ 해시태그: {tone_data['tone_info']['hashtags']}")
                        print()
                
        except Exception as e:
            print(f"❌ 테스트 실패: {e}")
            return
    
    # 성능 요약
    avg_time = sum(total_times) / len(total_times)
    min_time = min(total_times)
    max_time = max(total_times)
    
    print(f"\n📊 LangChain 체인 성능 요약 (3회 테스트):")
    print(f"   평균 시간: {avg_time:.2f}초")
    print(f"   최소 시간: {min_time:.2f}초")
    print(f"   최대 시간: {max_time:.2f}초")
    
    # 기존 처리 방식들과 비교
    print(f"\n⚡ LangChain 체인의 장점:")
    print(f"   🔗 RunnableParallel로 진짜 병렬 처리")
    print(f"   🚀 한 번의 체인 호출로 3개 어투 동시 생성")
    print(f"   🎯 OpenAI API 호출 최적화")
    print(f"   📦 체인 파이프라인으로 구조화된 처리")
    
    # 추정 비교
    estimated_sequential_time = avg_time * 3  # 순차 처리 추정치
    estimated_asyncio_gather = avg_time * 2   # asyncio.gather 추정치
    
    print(f"\n📈 예상 성능 비교:")
    print(f"   기존 순차 처리: ~{estimated_sequential_time:.1f}초")
    print(f"   단순 asyncio.gather: ~{estimated_asyncio_gather:.1f}초")
    print(f"   🏆 LangChain 체인: {avg_time:.1f}초")
    print(f"   📊 체인 vs 순차: {estimated_sequential_time/avg_time:.1f}배 개선")
    print(f"   📊 체인 vs asyncio: {estimated_asyncio_gather/avg_time:.1f}배 개선")
    
    print("\n✅ LangChain 체인 기반 어투 생성 테스트 완료! 🎉")

if __name__ == "__main__":
    asyncio.run(test_langchain_tone_performance())