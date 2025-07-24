#!/usr/bin/env python3
"""
멀티턴 대화 데이터셋을 활용한 파인튜닝 테스트 스크립트
"""

import asyncio
import httpx
import json
import sys
import os

# vllm 모듈을 import하기 위해 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'vllm'))

from vllm.app.utils.finetuning_utils import convert_qa_data_for_finetuning


async def test_multi_turn_qa_generation():
    """멀티턴 QA 생성 테스트"""
    
    print("="*50)
    print("🧪 멀티턴 대화 생성 테스트")
    print("="*50)
    
    # 테스트 캐릭터 데이터
    test_characters = [
        {
            "name": "테스트 캐릭터",
            "description": "활발하고 긍정적인 20대 여성",
            "age_range": "20-25세",
            "gender": "FEMALE",
            "personality": "친근하고 호기심이 많음",
            "mbti": "ENFP"
        }
    ]
    
    # 1. 멀티턴 QA 배치 생성 요청
    print("\n1. 멀티턴 QA 배치 생성 요청...")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/speech/generate_qa_batch",
            json={
                "characters": test_characters,
                "num_qa_per_character": 2,  # 테스트용으로 2개만
                "domains": ["일상생활", "과학기술"]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get("task_id")
            print(f"✅ 배치 생성 요청 성공! Task ID: {task_id}")
            
            # 2. 작업 상태 확인
            await asyncio.sleep(2)
            status_response = await client.get(
                f"http://localhost:8000/speech/qa_status/{task_id}"
            )
            
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"📊 작업 상태: {status.get('status')}")
                
                if status.get('status') == 'completed':
                    batch_requests = status.get('batch_requests', [])
                    print(f"✅ 생성된 배치 요청 수: {len(batch_requests)}")
                    
                    # 3. 첫 번째 요청 샘플 확인
                    if batch_requests:
                        first_request = batch_requests[0]
                        user_content = first_request.get('body', {}).get('messages', [])[1].get('content', '')
                        print(f"\n📝 첫 번째 요청 내용:")
                        print(user_content[:200] + "...")
                        
                        # 멀티턴 대화 생성이 요청되었는지 확인
                        if "7턴의 자연스러운 멀티턴 대화" in user_content:
                            print("✅ 멀티턴 대화 생성 프롬프트 확인!")
                        else:
                            print("❌ 멀티턴 대화 프롬프트가 없습니다.")
        else:
            print(f"❌ 요청 실패: {response.status_code}")
            print(response.text)


def test_finetuning_data_conversion():
    """파인튜닝 데이터 변환 테스트"""
    
    print("\n" + "="*50)
    print("🧪 파인튜닝 데이터 변환 테스트")
    print("="*50)
    
    # 테스트용 멀티턴 대화 데이터
    test_multi_turn_conversations = [
        [
            {"q": "오늘 날씨가 어때?", "a": "오늘은 정말 화창하고 좋은 날씨예요! 햇살이 따뜻해서 기분이 좋아져요."},
            {"q": "그럼 뭘 하면 좋을까?", "a": "이런 날엔 산책하거나 피크닉 가는 것도 좋겠어요! 저라면 친구들과 함께 공원에서 시간을 보낼 것 같아요."},
            {"q": "혼자서도 즐길 수 있는 활동은?", "a": "혼자서도 충분히 즐거울 수 있어요! 책을 들고 카페 테라스에서 읽거나, 음악 들으며 조깅하는 것도 추천해요."},
            {"q": "실내에서는 뭘 할 수 있을까?", "a": "실내에서도 할 게 많죠! 요리나 베이킹을 시도해보거나, 좋아하는 영화를 보는 것도 좋아요."},
            {"q": "요리 추천해줄 수 있어?", "a": "간단하면서도 맛있는 파스타는 어때요? 알리오 올리오나 카르보나라 같은 걸 만들어보세요!"},
            {"q": "레시피가 복잡하지 않을까?", "a": "전혀 복잡하지 않아요! 기본 재료 몇 가지만 있으면 20분 안에 완성할 수 있어요. 유튜브 보면서 따라하면 쉬워요."},
            {"q": "고마워, 도움이 됐어!", "a": "별말씀을요! 즐거운 하루 보내세요. 맛있는 요리 만들어서 행복한 시간 되길 바라요! 😊"}
        ],
        [
            {"q": "AI 기술이 얼마나 발전했어?", "a": "정말 놀라울 정도로 발전했어요! 이제 AI가 그림도 그리고, 음악도 만들고, 심지어 코딩도 도와줘요."},
            {"q": "인간의 창의성을 대체할 수 있을까?", "a": "완전히 대체하기는 어려울 것 같아요. AI는 도구로서 인간의 창의성을 증폭시키는 역할을 하죠."},
            {"q": "어떤 분야에서 가장 유용해?", "a": "의료, 교육, 엔터테인먼트 등 다양한 분야에서 활용되고 있어요. 특히 반복적인 작업을 자동화하는 데 탁월해요."},
            {"q": "부작용은 없을까?", "a": "물론 우려사항도 있죠. 일자리 변화, 프라이버시 문제, 윤리적 딜레마 등을 신중히 다뤄야 해요."},
            {"q": "개인이 어떻게 준비해야 할까?", "a": "AI와 협업하는 능력을 기르는 게 중요해요. 기술을 이해하고 활용하되, 인간만의 강점을 발전시켜야 해요."},
            {"q": "미래는 어떻게 될 것 같아?", "a": "AI와 인간이 공존하며 서로를 보완하는 세상이 될 거예요. 더 나은 미래를 만들기 위해 함께 노력해야 해요."},
            {"q": "희망적이네!", "a": "맞아요! 기술은 결국 우리가 어떻게 사용하느냐에 달려 있으니까요. 긍정적인 변화를 만들어갈 수 있을 거예요!"}
        ]
    ]
    
    # 파인튜닝 데이터로 변환
    finetuning_data = convert_qa_data_for_finetuning(
        test_multi_turn_conversations,
        "테스트 캐릭터",
        "ENFP - 친근하고 활발한 성격",
        "긍정적이고 밝은 어투 사용"
    )
    
    print(f"✅ 변환된 파인튜닝 데이터 수: {len(finetuning_data)}")
    
    # 첫 번째 데이터 샘플 확인
    if finetuning_data:
        first_data = finetuning_data[0]
        messages = first_data.get("messages", [])
        print(f"\n📝 첫 번째 대화 세션:")
        print(f"- 메시지 수: {len(messages)}")
        print(f"- 시스템 메시지: {messages[0]['content'][:100]}...")
        
        # 멀티턴 확인
        user_messages = [m for m in messages if m['role'] == 'user']
        assistant_messages = [m for m in messages if m['role'] == 'assistant']
        print(f"- 사용자 메시지 수: {len(user_messages)}")
        print(f"- 어시스턴트 메시지 수: {len(assistant_messages)}")
        
        if len(user_messages) == 7 and len(assistant_messages) == 7:
            print("✅ 7턴 멀티턴 대화가 올바르게 변환되었습니다!")
        else:
            print("❌ 멀티턴 대화 변환에 문제가 있습니다.")
            
        # 대화 흐름 샘플
        print("\n🔍 대화 흐름 샘플:")
        for i in range(min(3, len(user_messages))):
            print(f"\nTurn {i+1}:")
            print(f"Q: {user_messages[i]['content'][:50]}...")
            print(f"A: {assistant_messages[i]['content'][:50]}...")


if __name__ == "__main__":
    print("🚀 멀티턴 대화 파인튜닝 테스트 시작...\n")
    
    # 비동기 테스트 실행
    asyncio.run(test_multi_turn_qa_generation())
    
    # 동기 테스트 실행
    test_finetuning_data_conversion()
    
    print("\n✅ 테스트 완료!")