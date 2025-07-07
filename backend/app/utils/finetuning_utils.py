"""
파인튜닝 관련 공통 유틸리티 함수들
VLLM 서버와 로컬 파인튜닝에서 공통으로 사용되는 로직
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def create_system_message(influencer_name: str, personality: str, style_info: str = "") -> str:
    """
    인플루언서용 시스템 메시지 생성
    Args:
        influencer_name: 인플루언서 이름
        personality: 성격 정보
        style_info: 스타일 정보
    Returns:
        시스템 메시지
    """
    system_msg = f"""당신은 {influencer_name}입니다.

성격과 특징:
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
    """
    QA 데이터를 파인튜닝용 형식으로 변환
    Args:
        qa_data: QA 쌍 리스트
        influencer_name: 인플루언서 이름
        personality: 성격 정보
        style_info: 스타일 정보
    Returns:
        파인튜닝용 데이터
    """
    finetuning_data = []
    
    # 시스템 메시지 생성
    system_message = create_system_message(influencer_name, personality, style_info)
    print(qa_data)
    for qa_pair in qa_data:
        question = qa_pair.get('question', '').strip()
        answer = qa_pair.get('answer', '').strip()
        
        if not question:
            logger.error(f"QA 쌍에서 'question' 필드를 찾을 수 없거나 비어 있습니다: {qa_pair}")
        if not answer:
            logger.error(f"QA 쌍에서 'answer' 필드를 찾을 수 없거나 비어 있습니다: {qa_pair}")

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
    
    logger.info(f"QA 데이터 변환 완료: {len(qa_data)}개 → {len(finetuning_data)}개")
    return finetuning_data


def validate_qa_data(qa_data: List[Dict]) -> bool:
    """
    QA 데이터 유효성 검증
    Args:
        qa_data: 검증할 QA 데이터
    Returns:
        유효성 여부
    """
    if not qa_data:
        logger.error("QA 데이터가 비어있습니다.")
        return False
    
    valid_count = 0
    for i, qa_pair in enumerate(qa_data):
        if not isinstance(qa_pair, dict):
            logger.error(f"QA 쌍 {i}가 딕셔너리가 아닙니다: {type(qa_pair)}")
            continue
            
        question = qa_pair.get('question', '').strip()
        answer = qa_pair.get('answer', '').strip()
        
        if question and answer:
            valid_count += 1
        else:
            logger.warning(f"QA 쌍 {i}에 빈 질문 또는 답변: question={bool(question)}, answer={bool(answer)}")
    
    logger.info(f"QA 데이터 검증 결과: {valid_count}/{len(qa_data)}개 유효")
    
    # 최소 50% 이상이 유효해야 함
    return (valid_count / len(qa_data)) >= 0.5


def extract_influencer_info_from_repo(hf_repo_id: str) -> tuple[str, str]:
    """
    HuggingFace 레포지토리 ID에서 인플루언서 정보 추출
    Args:
        hf_repo_id: HuggingFace 레포지토리 ID (예: "username/model-name-finetuned")
    Returns:
        (username, model_name) 튜플
    """
    try:
        if '/' in hf_repo_id:
            username, repo_name = hf_repo_id.split('/', 1)
            model_name = repo_name.replace('-finetuned', '').replace('_finetuned', '')
            return username, model_name
        else:
            return "unknown", hf_repo_id
    except Exception as e:
        logger.error(f"레포지토리 ID 파싱 실패: {hf_repo_id}, {e}")
        return "unknown", "unknown"


def create_training_config(epochs: int = 5, learning_rate: float = 2e-4, 
                          batch_size: int = 4, gradient_accumulation: int = 2) -> Dict[str, Any]:
    """
    파인튜닝 학습 설정 생성
    Args:
        epochs: 학습 에포크 수
        learning_rate: 학습률
        batch_size: 배치 크기
        gradient_accumulation: 그래디언트 누적 단계
    Returns:
        학습 설정 딕셔너리
    """
    return {
        "num_train_epochs": epochs,
        "learning_rate": learning_rate,
        "per_device_train_batch_size": batch_size,
        "gradient_accumulation_steps": gradient_accumulation,
        "warmup_ratio": 0.1,
        "lr_scheduler_type": "cosine",
        "logging_steps": 10,
        "save_steps": 100,
        "eval_steps": 100,
        "save_total_limit": 2,
        "remove_unused_columns": False,
        "push_to_hub": True,
        "report_to": None,  # wandb 등 비활성화
    }


def format_model_name_for_korean(korean_name: str) -> str:
    """
    한글 이름을 모델명에 적합한 영문으로 변환
    Args:
        korean_name: 한글 이름
    Returns:
        영문 변환된 이름
    """
    # 간단한 한글 단어 매핑
    name_mapping = {
        '루시우': 'lucio',
        '아나': 'ana', 
        '메르시': 'mercy',
        '트레이서': 'tracer',
        '위도우메이커': 'widowmaker',
        '솔져': 'soldier',
        '라인하르트': 'reinhardt',
        '디바': 'dva',
        '윈스턴': 'winston',
        '겐지': 'genji',
        '한조': 'hanzo',
        '파라': 'pharah',
        '리퍼': 'reaper',
        '토르비욘': 'torbjorn',
        '바스티온': 'bastion',
        '시메트라': 'symmetra',
        '젠야타': 'zenyatta'
    }
    
    # 직접 매핑이 있는 경우 사용
    if korean_name in name_mapping:
        return name_mapping[korean_name]
    
    # 간단한 변환: 영문자와 숫자만 남기고 나머지는 제거
    result = ""
    for char in korean_name:
        if char.isalnum():
            if 'a' <= char <= 'z' or 'A' <= char <= 'Z' or '0' <= char <= '9':
                result += char.lower()
            else:
                # 한글인 경우 간단히 처리
                result += 'ko'
        elif char in ['-', '_']:
            result += char
    
    # 결과가 비어있거나 너무 짧으면 기본값 사용
    if not result or len(result) < 2:
        result = f"influencer_{hash(korean_name) % 10000}"
    
    return result