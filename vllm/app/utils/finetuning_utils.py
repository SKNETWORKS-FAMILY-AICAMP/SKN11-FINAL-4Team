import logging
import json
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# MBTI 데이터셋 로드
MBTI_DATASET_PATH = "/workspace/SKN11-FINAL-4Team/vllm/pipeline/mbti_personality_dataset.json"
MBTI_PERSONALITIES = {}

try:
    if os.path.exists(MBTI_DATASET_PATH):
        with open(MBTI_DATASET_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            MBTI_PERSONALITIES = data.get("mbti_personalities", {})
        logger.info(f"MBTI 데이터셋 로드 완료: {len(MBTI_PERSONALITIES)}개 유형")
    else:
        logger.warning(f"MBTI 데이터셋 파일을 찾을 수 없습니다: {MBTI_DATASET_PATH}")
except Exception as e:
    logger.error(f"MBTI 데이터셋 로드 중 오류 발생: {e}")

def create_system_message(influencer_name: str, personality: str, style_info: str = "") -> str:
    """시스템 메시지 생성 (VLLM 서버용)"""
    system_msg = f"""당신은 {influencer_name}입니다.

"""
    
    mbti_info = MBTI_PERSONALITIES.get(personality.upper()) # 대소문자 구분 없이 찾기
    
    if mbti_info:
        system_msg += f"""MBTI 유형: {mbti_info['name']} ({personality.upper()})
설명: {mbti_info['description']}
주요 특징: {', '.join(mbti_info['traits'])}

"""
        if mbti_info.get('speech_patterns'):
            speech_patterns = mbti_info['speech_patterns']
            system_msg += f"""말투 및 화법:
  - 어조: {speech_patterns.get('tone', '정보 없음')}
  - 스타일: {speech_patterns.get('style', '정보 없음')}
  - 특징: {', '.join(speech_patterns.get('characteristics', []))}

"""
        if mbti_info.get('example_phrases'):
            system_msg += f"""예시 표현: {', '.join(mbti_info['example_phrases'])}

"""
    else:
        system_msg += f"""성격과 특징:
{personality}

"""
    
    if style_info:
        system_msg += f"""스타일 정보:
{style_info}

"""
    
    system_msg += f"""이 캐릭터의 성격과 말투를 완벽하게 재현하여 답변해주세요.
- 항상 캐릭터의 개성이 드러나도록 답변하세요
- 일관된 말투와 어조를 유지하세요
- 캐릭터의 특징적인 표현이나 어미를 사용하세요
- 자연스럽고 매력적인 대화를 이끌어가세요"""
    
    return system_msg

def convert_qa_data_for_finetuning(qa_data: List[Dict], influencer_name: str, 
                                 personality: str, style_info: str = "") -> List[Dict]:
    """QA 데이터를 파인튜닝용 형식으로 변환 (VLLM 서버용)"""
    finetuning_data = []

    logger.info(f"convert_qa_data_for_finetuning: Received {len(qa_data)} QA pairs.")
    if not qa_data:
        logger.warning("convert_qa_data_for_finetuning: qa_data is empty.")
        return []

    # 시스템 메시지 생성
    system_message = create_system_message(influencer_name, personality, style_info)
    print(qa_data)
    for i, qa_pair in enumerate(qa_data):
        question = qa_pair.get('question', '').strip()
        answer = qa_pair.get('answer', '').strip()

        if not question:
            logger.warning(f"convert_qa_data_for_finetuning: QA pair {i} has empty question: {qa_pair}")
        if not answer:
            logger.warning(f"convert_qa_data_for_finetuning: QA pair {i} has empty answer: {qa_pair}")

        if question and answer:
            # EXAONE 모델용 채팅 형식으로 변환
            formatted_data = {
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer}
                ]
            }
            finetuning_data.append(formatted_data)
        else:
            logger.warning(f"convert_qa_data_for_finetuning: Skipping invalid QA pair {i}: {qa_pair}")

    logger.info(f"QA 데이터 변환 완료: {len(qa_data)}개 → {len(finetuning_data)}개")
    return finetuning_data
