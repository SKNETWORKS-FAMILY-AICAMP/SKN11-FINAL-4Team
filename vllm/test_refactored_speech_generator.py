#!/usr/bin/env python3
"""
리팩토링된 speech_generator 테스트
"""

import asyncio
import os
from dotenv import load_dotenv
from pipeline.speech_generator import SpeechGenerator, CharacterProfile, Gender

# 환경 변수 로드
load_dotenv()

async def test_refactored_methods():
    """리팩토링된 메서드들 테스트"""
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
        return
    
    # 테스트 캐릭터
    character = CharacterProfile(
        name="테스트봇",
        description="친근하고 유머러스한 AI 어시스턴트",
        age_range="20-30대",
        gender=Gender.NON_BINARY,
        personality="밝고 긍정적이며 도움을 주는 것을 좋아함",
        mbti="ENFP"
    )
    
    # SpeechGenerator 인스턴스 생성
    generator = SpeechGenerator(api_key=api_key)
    
    print("🧪 리팩토링된 speech_generator 테스트")
    print("=" * 50)
    
    try:
        # 1. 시스템 프롬프트 생성 테스트
        print("\n1️⃣ 시스템 프롬프트 생성 테스트")
        system_prompt = await generator.generate_system_prompt_with_gpt(character)
        print(f"✅ 시스템 프롬프트 생성 완료 (길이: {len(system_prompt)}자)")
        
        # 2. 질문 생성 테스트
        print("\n2️⃣ 질문 생성 테스트")
        question = await generator.generate_question_for_character(character)
        print(f"✅ 생성된 질문: {question}")
        
        # 3. 어투 요약 테스트
        print("\n3️⃣ 어투 요약 테스트")
        summary = await generator.summarize_speech_style_with_gpt(system_prompt)
        print(f"✅ 해시태그: {summary.get('hashtags', 'N/A')}")
        print(f"✅ 설명: {summary.get('description', 'N/A')}")
        
        # 4. 3가지 어투 생성 테스트
        print("\n4️⃣ 3가지 어투 생성 테스트")
        tones = await generator.generate_character_tones_for_question(character, question, 3)
        for tone_name, tone_list in tones.items():
            if tone_list:
                print(f"✅ {tone_name}: {tone_list[0]['text'][:50]}...")
        
        # 5. 랜덤 어투 설명 생성 테스트
        print("\n5️⃣ 랜덤 어투 설명 생성 테스트")
        descriptions = await generator.get_random_tone_descriptions(character)
        for tone_name, desc in descriptions.items():
            print(f"✅ {tone_name}: {desc}")
        
        # 6. 헬퍼 메서드 테스트
        print("\n6️⃣ 헬퍼 메서드 테스트")
        char_info = generator._format_character_info(character)
        print(f"✅ 캐릭터 정보 포맷팅 완료 (길이: {len(char_info)}자)")
        
        # 7. MBTI 유효성 검사 테스트
        print("\n7️⃣ MBTI 유효성 검사 테스트")
        print(f"✅ 유효한 MBTI 타입 수: {len(generator.VALID_MBTI_TYPES)}")
        print(f"✅ ENFP는 유효한가? {'ENFP' in generator.VALID_MBTI_TYPES}")
        
        print("\n" + "=" * 50)
        print("✅ 모든 테스트 완료! 리팩토링이 성공적으로 작동합니다.")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

async def test_api_call_method():
    """_call_openai_api 메서드 직접 테스트"""
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
        return
    
    generator = SpeechGenerator(api_key=api_key)
    
    print("\n" + "=" * 50)
    print("🔧 _call_openai_api 메서드 테스트")
    print("-" * 50)
    
    try:
        messages = [
            {"role": "system", "content": "당신은 친절한 AI 어시스턴트입니다."},
            {"role": "user", "content": "안녕하세요! 오늘 기분이 어떠세요?"}
        ]
        
        # 다양한 매개변수로 테스트
        print("\n1. 기본 매개변수 테스트")
        response1 = await generator._call_openai_api(messages)
        print(f"✅ 응답: {response1[:50]}...")
        
        print("\n2. 높은 temperature 테스트")
        response2 = await generator._call_openai_api(messages, temperature=1.0)
        print(f"✅ 응답: {response2[:50]}...")
        
        print("\n3. 긴 응답 테스트")
        response3 = await generator._call_openai_api(messages, max_tokens=300)
        print(f"✅ 응답 길이: {len(response3)}자")
        
        print("\n✅ _call_openai_api 메서드가 정상적으로 작동합니다!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 메인 테스트 실행
    asyncio.run(test_refactored_methods())
    
    # API 호출 메서드 테스트
    asyncio.run(test_api_call_method())