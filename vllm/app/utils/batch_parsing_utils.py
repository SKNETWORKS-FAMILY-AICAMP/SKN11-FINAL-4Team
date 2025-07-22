"""
배치 처리 결과 파싱 유틸리티
OpenAI Batch API 결과를 파싱하여 멀티턴 대화 데이터 추출
"""

import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def parse_batch_results(batch_response_file: str) -> List[List[Dict[str, str]]]:
    """
    배치 API 결과 파일을 파싱하여 멀티턴 대화 데이터 추출
    
    Args:
        batch_response_file: OpenAI Batch API 응답 JSONL 파일 경로
        
    Returns:
        List[List[Dict]]: 멀티턴 대화 리스트
        예: [[{"q": "질문1", "a": "답변1"}, {"q": "질문2", "a": "답변2"}], ...]
    """
    multi_turn_conversations = []
    
    try:
        with open(batch_response_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue
                    
                try:
                    # JSONL 라인 파싱
                    response = json.loads(line)
                    
                    # 응답 구조 확인
                    if response.get("response", {}).get("status_code") == 200:
                        # 성공한 응답에서 대화 데이터 추출
                        body = response.get("response", {}).get("body", {})
                        choices = body.get("choices", [])
                        
                        if choices and len(choices) > 0:
                            content = choices[0].get("message", {}).get("content", "")
                            
                            try:
                                # JSON 형식의 멀티턴 대화 파싱
                                conversation = json.loads(content)
                                
                                # 리스트 형식 확인
                                if isinstance(conversation, list) and all(
                                    isinstance(turn, dict) and 'q' in turn and 'a' in turn 
                                    for turn in conversation
                                ):
                                    multi_turn_conversations.append(conversation)
                                    logger.debug(f"Line {line_num}: 성공적으로 {len(conversation)}턴 대화 추출")
                                else:
                                    logger.warning(f"Line {line_num}: 잘못된 대화 형식: {conversation}")
                                    
                            except json.JSONDecodeError as e:
                                logger.error(f"Line {line_num}: 대화 내용 JSON 파싱 실패: {e}")
                                logger.debug(f"Content: {content[:200]}...")
                    else:
                        # 실패한 응답 로깅
                        error = response.get("error", {})
                        logger.warning(f"Line {line_num}: API 요청 실패 - {error}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Line {line_num}: JSONL 라인 파싱 실패: {e}")
                    logger.debug(f"Line content: {line[:200]}...")
                    
    except FileNotFoundError:
        logger.error(f"배치 결과 파일을 찾을 수 없습니다: {batch_response_file}")
    except Exception as e:
        logger.error(f"배치 결과 파싱 중 오류 발생: {e}")
    
    logger.info(f"총 {len(multi_turn_conversations)}개의 멀티턴 대화 추출 완료")
    return multi_turn_conversations


def convert_multi_turn_for_finetuning(
    multi_turn_conversations: List[List[Dict[str, str]]], 
    character_name: str,
    personality: str,
    style_info: str = ""
) -> List[Dict[str, Any]]:
    """
    멀티턴 대화 데이터를 파인튜닝용 형식으로 변환
    
    Args:
        multi_turn_conversations: 멀티턴 대화 리스트
        character_name: 캐릭터 이름
        personality: 캐릭터 성격
        style_info: 추가 스타일 정보
        
    Returns:
        List[Dict]: 파인튜닝용 데이터
    """
    from app.utils.finetuning_utils import convert_qa_data_for_finetuning
    
    # convert_qa_data_for_finetuning 함수가 멀티턴을 지원하도록 수정되었으므로
    # 그대로 전달하면 됨
    return convert_qa_data_for_finetuning(
        multi_turn_conversations, 
        character_name, 
        personality, 
        style_info
    )


def extract_qa_from_batch_file(batch_file_path: str) -> Dict[str, List[List[Dict[str, str]]]]:
    """
    배치 파일에서 캐릭터별 멀티턴 대화 추출
    
    Args:
        batch_file_path: 배치 결과 파일 경로
        
    Returns:
        Dict[str, List]: 캐릭터 이름을 키로 하는 멀티턴 대화 딕셔너리
    """
    character_conversations = {}
    
    try:
        with open(batch_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                    
                try:
                    response = json.loads(line)
                    custom_id = response.get("custom_id", "")
                    
                    # custom_id에서 캐릭터 이름 추출 (예: "qa_캐릭터이름_도메인_0_0")
                    parts = custom_id.split("_")
                    if len(parts) >= 3 and parts[0] == "qa":
                        character_name = parts[1]
                        
                        if response.get("response", {}).get("status_code") == 200:
                            body = response.get("response", {}).get("body", {})
                            choices = body.get("choices", [])
                            
                            if choices:
                                content = choices[0].get("message", {}).get("content", "")
                                try:
                                    conversation = json.loads(content)
                                    if isinstance(conversation, list):
                                        if character_name not in character_conversations:
                                            character_conversations[character_name] = []
                                        character_conversations[character_name].append(conversation)
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to parse conversation for {character_name}")
                                    
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSONL line")
                    
    except Exception as e:
        logger.error(f"Error extracting QA from batch file: {e}")
    
    return character_conversations