"""
대사 분석을 위한 OpenAI API 활용 라우터
캐릭터의 대사를 분석하여 시스템 프롬프트를 생성
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import os
from openai import OpenAI

router = APIRouter()
logger = logging.getLogger(__name__)

# OpenAI 클라이언트 초기화
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.warning("⚠️ OPENAI_API_KEY가 설정되지 않았습니다. 대사 분석 기능이 제한될 수 있습니다.")
    openai_client = None
else:
    openai_client = OpenAI(api_key=openai_api_key)
    logger.info("✅ OpenAI 클라이언트 초기화 완료")


class ToneAnalysisRequest(BaseModel):
    """대사 분석 요청 모델"""
    tone_data: str
    character_info: Optional[Dict[str, Any]] = None


class ToneAnalysisResponse(BaseModel):
    """대사 분석 응답 모델"""
    system_prompt: str
    tone_analysis: str
    original_tone_data: str


@router.post("/analyze_tone", response_model=ToneAnalysisResponse)
async def analyze_tone_data(request: ToneAnalysisRequest):
    """
    대사 데이터를 분석하여 시스템 프롬프트 생성
    
    Args:
        request: 분석할 대사 데이터와 캐릭터 정보
        
    Returns:
        ToneAnalysisResponse: 생성된 시스템 프롬프트와 분석 결과
    """
    if not openai_client:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key not configured. Cannot analyze tone data."
        )
    
    try:
        # 분석 프롬프트 구성
        analysis_prompt = f"""다음 대사들을 분석하여 이 캐릭터의 말투 특징을 파악하고, 적절한 시스템 프롬프트를 생성해주세요.

대사:
{request.tone_data}

"""
        # 캐릭터 정보 추출
        char_name = "알 수 없음"
        char_description = "설명 없음"
        char_personality = "성격 정보 없음"
        char_mbti = "MBTI 정보 없음"
        char_age = "연령대 정보 없음"
        char_gender = "성별 정보 없음"
        
        if request.character_info:
            char_name = str(request.character_info.get('name', '알 수 없음'))
            char_description = str(request.character_info.get('description', '설명 없음'))
            char_personality = str(request.character_info.get('personality', '성격 정보 없음'))
            char_mbti = str(request.character_info.get('mbti', 'MBTI 정보 없음'))
            char_age = str(request.character_info.get('age', '연령대 정보 없음'))
            char_gender = str(request.character_info.get('gender', '성별 정보 없음'))
            
            analysis_prompt += f"""
캐릭터 정보:
- 이름: {char_name}
- 설명: {char_description}
- 성격: {char_personality}
- MBTI: {char_mbti}
- 연령대: {char_age}
- 성별: {char_gender}
"""

        analysis_prompt += """
다음 형식으로 응답해주세요:

1. 말투 분석:
- 어체 특징: (존댓말/반말, 격식/비격식 등)
- 어미 사용: (특징적인 어미나 종결어)
- 특수 표현: (자주 사용하는 감탄사, 별명, 특정 단어 등)
- 감정 표현: (감정 표현 방식의 특징)

2. 시스템 프롬프트:
당신은 이제 [캐릭터 이름] 라는 캐릭터처럼 대화해야 합니다.
[캐릭터 정보]
- 이름: [캐릭터 이름]
- 설명: [캐릭터 설명]
- 성격: [캐릭터 성격]
- MBTI: [캐릭터 MBTI]
- 연령대: [캐릭터 연령대]
- 성별: [캐릭터 성별]

[말투 지시사항]
[위 대사 분석을 바탕으로 작성한 구체적인 말투 지시사항]

[주의사항]
[캐릭터가 지켜야 할 대화 규칙과 주의사항]

3. 대표 예시:
위 대사 중 가장 특징적인 2-3개를 선별해주세요.
"""

        logger.info("🔍 OpenAI API를 통한 대사 분석 시작")
        
        # OpenAI API 호출
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # 또는 "gpt-3.5-turbo"
            messages=[
                {
                    "role": "system",
                    "content": "당신은 캐릭터의 대사를 분석하여 말투 특징을 파악하고 시스템 프롬프트를 생성하는 전문가입니다."
                },
                {
                    "role": "user",
                    "content": analysis_prompt
                }
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        analysis_text = response.choices[0].message.content
        
        # 분석 결과에서 시스템 프롬프트 추출
        system_prompt = ""
        if "2. 시스템 프롬프트:" in analysis_text:
            prompt_start = analysis_text.find("2. 시스템 프롬프트:") + len("2. 시스템 프롬프트:")
            prompt_end = analysis_text.find("\n3.", prompt_start)
            if prompt_end == -1:
                prompt_end = len(analysis_text)
            system_prompt = analysis_text[prompt_start:prompt_end].strip()
            
            # 플레이스홀더를 실제 값으로 치환
            system_prompt = system_prompt.replace("[캐릭터 이름]", char_name)
            system_prompt = system_prompt.replace("[캐릭터 설명]", char_description)
            system_prompt = system_prompt.replace("[캐릭터 성격]", char_personality)
            system_prompt = system_prompt.replace("[캐릭터 MBTI]", char_mbti)
            system_prompt = system_prompt.replace("[캐릭터 연령대]", char_age)
            system_prompt = system_prompt.replace("[캐릭터 성별]", char_gender)
        
        # 시스템 프롬프트가 추출되지 않았으면 기본 형식으로 생성
        if not system_prompt or len(system_prompt) < 50:
            # 말투 분석 결과에서 지시사항 추출 시도
            tone_instructions = "대사에서 나타나는 말투 특징을 그대로 사용해주세요."
            cautions = "캐릭터의 성격과 일관성 있게 대화해주세요."
            
            if "말투 지시사항" in analysis_text:
                inst_start = analysis_text.find("[말투 지시사항]")
                inst_end = analysis_text.find("[주의사항]", inst_start)
                if inst_start != -1 and inst_end != -1:
                    tone_instructions = analysis_text[inst_start:inst_end].replace("[말투 지시사항]", "").strip()
            
            if "주의사항" in analysis_text:
                caut_start = analysis_text.find("[주의사항]")
                caut_end = analysis_text.find("\n3.", caut_start)
                if caut_start != -1:
                    if caut_end == -1:
                        caut_end = len(analysis_text)
                    cautions = analysis_text[caut_start:caut_end].replace("[주의사항]", "").strip()
            
            system_prompt = f"""당신은 이제 {char_name} 라는 캐릭터처럼 대화해야 합니다.
[캐릭터 정보]
- 이름: {char_name}
- 설명: {char_description}
- 성격: {char_personality}
- MBTI: {char_mbti}
- 연령대: {char_age}
- 성별: {char_gender}

[말투 지시사항]
{tone_instructions}

[주의사항]
{cautions}"""
        
        logger.info(f"✅ 대사 분석 완료 - 시스템 프롬프트: {system_prompt[:100]}...")
        
        return ToneAnalysisResponse(
            system_prompt=system_prompt,
            tone_analysis=analysis_text,
            original_tone_data=request.tone_data
        )
        
    except Exception as e:
        logger.error(f"❌ 대사 분석 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze tone data: {str(e)}"
        )


@router.get("/analyze_tone/health")
async def health_check():
    """대사 분석 서비스 상태 확인"""
    return {
        "status": "healthy" if openai_client else "limited",
        "openai_configured": openai_client is not None,
        "message": "Tone analysis service is ready" if openai_client else "OpenAI API key not configured"
    }