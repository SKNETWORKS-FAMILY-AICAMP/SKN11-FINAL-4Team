#!/usr/bin/env python3
"""
해시태그 생성 테스트
"""

import asyncio
import os
import json
from dotenv import load_dotenv
from app.utils.langchain_tone_generator import LangChainToneGenerator

# 환경 변수 로드
load_dotenv()

async def test_hashtag_generation():
    """해시태그 생성 테스트"""
    
    # API 키 확인
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
        return
    
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
    
    print("🧪 해시태그 생성 테스트")
    print(f"📝 캐릭터: {test_character['name']}")
    print(f"❓ 질문: {test_question}")
    print("-" * 50)
    
    # LangChain 어투 생성기
    tone_generator = LangChainToneGenerator(api_key=api_key)
    
    try:
        # 3개 어투 생성
        responses = await tone_generator.generate_3_tones_parallel(
            character_data=test_character,
            question=test_question
        )
        
        print("\n✅ 생성 완료!")
        print("-" * 50)
        
        # 결과 출력
        for tone_name, tone_responses in responses.items():
            print(f"\n🎭 {tone_name}:")
            for response in tone_responses:
                print(f"   📝 텍스트: {response['text'][:100]}...")
                print(f"   🏷️  해시태그: {response.get('hashtags', 'N/A')}")
                print(f"   📋 설명: {response.get('description', 'N/A')}")
                
                # 해시태그 검증
                hashtags = response.get('hashtags', '')
                if hashtags and hashtags != f"#말투1 #말투" and "#말투1" not in hashtags:
                    print(f"   ✅ 해시태그가 제대로 생성됨!")
                else:
                    print(f"   ⚠️  기본 해시태그가 사용됨")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

async def test_summary_prompt():
    """요약 프롬프트 직접 테스트"""
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
        return
    
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    
    print("\n" + "=" * 50)
    print("🔍 요약 프롬프트 직접 테스트")
    print("-" * 50)
    
    # LLM 초기화
    llm = ChatOpenAI(
        api_key=api_key,
        model="gpt-4o-mini",
        temperature=0.7
    )
    
    # 테스트 시스템 프롬프트
    test_system_prompt = """당신은 이제 '루나'라는 캐릭터처럼 대화해야 합니다.

[캐릭터 정보]
- 이름: 루나
- 설명: 밝고 활발한 20대 여성, 새로운 것을 좋아함
- 성격: 친근하고 긍정적이며 호기심이 많음
- MBTI: ENFP
- 연령대: 20-25세
- 성별: 여성

[말투 지시사항]
주어진 캐릭터 정보를 바탕으로 첫 번째 독특하고 창의적인 말투로 답변하세요. 캐릭터의 특성을 반영하되 예상치 못한 방식으로 표현해주세요.

[주의사항]
- 캐릭터의 성격과 말투를 일관성 있게 유지하세요
- 자연스럽고 매력적인 대화를 하세요
- 주어진 질문에 캐릭터답게 답변하세요
- 말투의 특징을 잘 드러내세요"""
    
    # 요약 프롬프트
    summary_prompt = ChatPromptTemplate.from_messages([
        ("system", """주어진 말투의 system prompt를 기반으로 그 말투의 특징을 요약해주세요. 반드시 아래 형식을 그대로 지켜서 JSON으로 출력하세요.
            형식:
            {{
                "hashtags": "#키워드1 #키워드2 #키워드3",
                "description": "말투 설명 (한 문장, '~말투'로 끝나야 함)"
            }}

            조건:
            1. 말투 스타일을 MZ 느낌나게 키워드 3개를 생성해 해시태그 형식으로 작성해 주세요.
            2. 말투 스타일을 한 문장으로 요약해주세요. 반드시 '말투'로 끝나야 합니다. 서술어 없이 명사형으로 끝납니다.
            3. 출력 형식은 반드시 JSON 형식으로 반환해주세요. (추가 설명 없이)"""),
        ("user", "말투 지시사항:\n{system_prompt}")
    ])
    
    try:
        # 프롬프트 실행
        chain = summary_prompt | llm
        result = await chain.ainvoke({"system_prompt": test_system_prompt})
        
        print(f"🤖 LLM 응답:\n{result.content}")
        
        # JSON 파싱 시도
        import re
        json_match = re.search(r'\{[\s\S]*?\}', result.content)
        if json_match:
            json_str = json_match.group()
            parsed = json.loads(json_str)
            print(f"\n✅ 파싱된 JSON:")
            print(f"   해시태그: {parsed.get('hashtags')}")
            print(f"   설명: {parsed.get('description')}")
        else:
            print("\n❌ JSON 파싱 실패")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 50)
    print("🏷️  해시태그 생성 테스트")
    print("=" * 50)
    
    # 해시태그 생성 테스트
    asyncio.run(test_hashtag_generation())
    
    # 요약 프롬프트 직접 테스트
    asyncio.run(test_summary_prompt())