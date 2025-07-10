"""
QA쌍 생성 전용 라우터
인플루언서 파인튜닝을 위한 QA 데이터셋 생성
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import asyncio
import os
import json
import logging
from datetime import datetime
from openai import OpenAI
import httpx

from pipeline.speech_generator import CharacterProfile, Gender
# LangChain QA 생성은 제거 - 배치 처리 우선

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for QA generation tasks
qa_generation_tasks: Dict[str, Dict[str, Any]] = {}

# 도메인별 QA 생성을 위한 카테고리 정의
DOMAIN_CATEGORIES = [
    "일상생활",
    "과학기술", 
    "사회이슈",
    "인문학",
    "스포츠",
    "역사문화"
]

class CharacterData(BaseModel):
    """QA 생성용 캐릭터 데이터"""
    name: str
    description: Optional[str] = ""
    age_range: Optional[str] = "알 수 없음"
    gender: Optional[str] = "NON_BINARY"  # MALE, FEMALE, NON_BINARY
    personality: Optional[str] = "친근하고 활발한 성격"
    mbti: Optional[str] = None

class QAGenerationRequest(BaseModel):
    """QA 생성 요청"""
    character: CharacterData
    num_qa_pairs: int = 2000  # 생성할 QA 쌍 개수
    domains: Optional[List[str]] = None  # 특정 도메인 지정 (없으면 전체)
    system_prompt: Optional[str] = None

class QABatchRequest(BaseModel):
    """배치 QA 생성 요청"""
    characters: List[CharacterData]
    num_qa_per_character: int = 1
    domains: Optional[List[str]] = None
    system_prompt: Optional[str] = None

class BatchStatusRequest(BaseModel):
    """OpenAI 배치 상태 조회 요청"""
    batch_id: str

# LangChain 기반 고속 QA 생성은 제거 - 배치 처리가 비용 효율적

@router.post("/generate_qa_batch")
async def generate_qa_batch(
    request: QABatchRequest,
    background_tasks: BackgroundTasks
):
    """
    배치 QA 생성 (여러 캐릭터, OpenAI Batch API용)
    각 캐릭터별로 지정된 개수의 QA 쌍을 생성하여 JSONL 형식으로 반환
    """
    task_id = str(uuid.uuid4())
    
    # 도메인 설정 (지정되지 않은 경우 전체 도메인 사용)
    domains = request.domains if request.domains else DOMAIN_CATEGORIES
    
    qa_generation_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "completed": 0,
        "total_requests": len(request.characters) * request.num_qa_per_character,
        "batch_requests": [],
        "domains": domains,
        "error": None,
        "start_time": datetime.now().isoformat()
    }
    
    logger.info(f"QA 배치 생성 작업 시작: {task_id}, 캐릭터 수: {len(request.characters)}")
    
    # 백그라운드에서 QA 생성 실행
    background_tasks.add_task(
        _run_qa_batch_generation,
        task_id,
        request.characters,
        request.num_qa_per_character,
        domains,
        request.system_prompt
    )
    
    return {
        "task_id": task_id,
        "status": "accepted",
        "total_requests": qa_generation_tasks[task_id]["total_requests"],
        "domains": domains
    }

@router.post("/generate_qa_for_influencer")
async def generate_qa_for_influencer(
    request: QAGenerationRequest,
    background_tasks: BackgroundTasks
):
    """
    인플루언서용 대량 QA 생성 (단일 캐릭터, 2000개)
    파인튜닝을 위한 대량의 QA 쌍을 도메인별로 생성
    """
    task_id = str(uuid.uuid4())
    
    # 도메인 설정
    domains = request.domains if request.domains else DOMAIN_CATEGORIES
    
    # 도메인별 QA 개수 계산 (균등 분배)
    qa_per_domain = request.num_qa_pairs // len(domains)
    
    qa_generation_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "completed": 0,
        "total_qa_pairs": request.num_qa_pairs,
        "qa_per_domain": qa_per_domain,
        "domains": domains,
        "character": request.character.dict(),
        "batch_requests": [],
        "error": None,
        "start_time": datetime.now().isoformat()
    }
    
    logger.info(f"인플루언서 QA 생성 작업 시작: {task_id}, 총 {request.num_qa_pairs}개")
    
    # 백그라운드에서 대량 QA 생성 실행
    background_tasks.add_task(
        _run_influencer_qa_generation,
        task_id,
        request.character,
        request.num_qa_pairs,
        domains,
        request.system_prompt
    )
    
    return {
        "task_id": task_id,
        "status": "accepted",
        "total_qa_pairs": request.num_qa_pairs,
        "domains": domains,
        "qa_per_domain": qa_per_domain
    }

@router.get("/qa_status/{task_id}")
async def get_qa_generation_status(task_id: str):
    """QA 생성 작업 상태 조회"""
    task = qa_generation_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return task

@router.get("/qa_results/{task_id}")
async def get_qa_generation_results(task_id: str):
    """QA 생성 결과 조회"""
    task = qa_generation_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="작업이 아직 완료되지 않았습니다.")
    
    return {
        "task_id": task_id,
        "batch_requests": task["batch_requests"],
        "total_requests": len(task["batch_requests"]),
        "domains": task.get("domains", [])
    }

@router.post("/openai_batch_status")
async def get_openai_batch_status(request: BatchStatusRequest):
    """OpenAI 배치 작업 상태 조회"""
    try:
        # OpenAI 클라이언트 초기화
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 배치 상태 조회
        batch = client.batches.retrieve(request.batch_id)
        
        return {
            "batch_id": batch.id,
            "status": batch.status,
            "object": batch.object,
            "created_at": batch.created_at,
            "in_progress_at": batch.in_progress_at,
            "expires_at": batch.expires_at,
            "finalizing_at": batch.finalizing_at,
            "completed_at": batch.completed_at,
            "failed_at": batch.failed_at,
            "expired_at": batch.expired_at,
            "cancelling_at": batch.cancelling_at,
            "cancelled_at": batch.cancelled_at,
            "request_counts": batch.request_counts,
            "metadata": batch.metadata,
            "completion_window": batch.completion_window,
            "endpoint": batch.endpoint,
            "input_file_id": batch.input_file_id,
            "output_file_id": batch.output_file_id,
            "error_file_id": batch.error_file_id
        }
    except Exception as e:
        logger.error(f"OpenAI 배치 상태 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"배치 상태 조회 중 오류 발생: {str(e)}")

@router.get("/openai_batch_status/{batch_id}")
async def get_openai_batch_status_by_id(batch_id: str):
    """OpenAI 배치 작업 상태 조회 (GET 방식)"""
    try:
        # OpenAI 클라이언트 초기화
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 배치 상태 조회
        batch = client.batches.retrieve(batch_id)
        
        return {
            "batch_id": batch.id,
            "status": batch.status,
            "object": batch.object,
            "created_at": batch.created_at,
            "in_progress_at": batch.in_progress_at,
            "expires_at": batch.expires_at,
            "finalizing_at": batch.finalizing_at,
            "completed_at": batch.completed_at,
            "failed_at": batch.failed_at,
            "expired_at": batch.expired_at,
            "cancelling_at": batch.cancelling_at,
            "cancelled_at": batch.cancelled_at,
            "request_counts": batch.request_counts,
            "metadata": batch.metadata,
            "completion_window": batch.completion_window,
            "endpoint": batch.endpoint,
            "input_file_id": batch.input_file_id,
            "output_file_id": batch.output_file_id,
            "error_file_id": batch.error_file_id
        }
    except Exception as e:
        logger.error(f"OpenAI 배치 상태 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"배치 상태 조회 중 오류 발생: {str(e)}")

async def _run_qa_batch_generation(
    task_id: str,
    characters_data: List[CharacterData],
    num_qa_per_character: int,
    domains: List[str],
    system_prompt: Optional[str]
):
    """배치 QA 생성 실행 함수"""
    task_entry = qa_generation_tasks[task_id]
    task_entry["status"] = "processing"
    
    try:
        all_batch_requests = []
        
        for i, char_data in enumerate(characters_data):
            # CharacterProfile 생성
            character_profile = CharacterProfile(
                name=char_data.name,
                description=char_data.description,
                age_range=char_data.age_range,
                gender=Gender[char_data.gender.upper()] if char_data.gender else Gender.NON_BINARY,
                personality=char_data.personality,
                mbti=char_data.mbti
            )
            
            # 도메인별 특성 설명 (위와 동일)
            domain_descriptions = {
                "일상생활": "일상의 소소한 일들, 취미, 습관, 음식, 주말 활동 등",
                "과학기술": "AI, 기술 트렌드, 스마트폰, 미래 기술, 과학의 발전",
                "사회이슈": "사회 문제, 환경, 불평등, 세대 간 차이, 미래 사회",
                "인문학": "인생의 가치, 책, 예술, 철학, 역사의 교훈",
                "스포츠": "운동, 건강관리, 스포츠 경기, 운동의 즐거움",
                "역사문화": "전통문화, 역사적 장소, 문화의 다양성, 역사 인물"
            }
            
            # 도메인별로 QA 생성
            for domain in domains:
                for j in range(num_qa_per_character):
                    domain_desc = domain_descriptions.get(domain, domain)
                    
                    # OpenAI Batch API 형식으로 변환
                    custom_id = f"qa_{char_data.name}_{domain}_{i}_{j}"
                    batch_request = {
                        "custom_id": custom_id,
                        "method": "POST",
                        "url": "/v1/chat/completions",
                        "body": {
                            "model": "gpt-4o-mini",
                            "messages": [
                                {
                                    "role": "system", 
                                    "content": system_prompt or f"당신은 {char_data.name}라는 캐릭터입니다. {char_data.personality} 성격을 가지고 있습니다."
                                },
                                {
                                    "role": "user", 
                                    "content": f"""{domain}({domain_desc})에 관한 QA 쌍을 하나 만들어주세요.
{char_data.name}의 성격과 특성에 맞는 자연스럽고 흥미로운 질문을 만들고, 그에 대해 캐릭터답게 답변해주세요.
반드시 JSON 형식으로 답변해주세요:
{{"q": "질문 내용", "a": "답변 내용"}}"""
                                }
                            ],
                            "max_tokens": 500,
                            "temperature": 0.7,
                            "response_format": {"type": "json_object"}  # JSON 형식 강제
                        }
                    }
                    
                    all_batch_requests.append(batch_request)
                    task_entry["completed"] += 1
                    task_entry["progress"] = (task_entry["completed"] / task_entry["total_requests"]) * 100
                    
                    # 주기적으로 이벤트 루프에 제어권 반환
                    if task_entry["completed"] % 10 == 0:
                        await asyncio.sleep(0.01)
        
        # 결과 저장
        task_entry["batch_requests"] = all_batch_requests
        task_entry["status"] = "completed"
        task_entry["progress"] = 100
        task_entry["end_time"] = datetime.now().isoformat()
        
        logger.info(f"QA 배치 생성 완료: {task_id}, 총 {len(all_batch_requests)}개 생성")
        
    except Exception as e:
        task_entry["status"] = "failed"
        task_entry["error"] = str(e)
        task_entry["end_time"] = datetime.now().isoformat()
        logger.error(f"QA 배치 생성 실패: {task_id}, 오류: {e}", exc_info=True)

async def _run_influencer_qa_generation(
    task_id: str,
    character_data: CharacterData,
    total_qa_pairs: int,
    domains: List[str],
    system_prompt: Optional[str]
):
    """인플루언서용 대량 QA 생성 실행 함수"""
    task_entry = qa_generation_tasks[task_id]
    task_entry["status"] = "processing"
    
    try:
        # CharacterProfile 생성
        character_profile = CharacterProfile(
            name=character_data.name,
            description=character_data.description,
            age_range=character_data.age_range,
            gender=Gender[character_data.gender.upper()] if character_data.gender else Gender.NON_BINARY,
            personality=character_data.personality,
            mbti=character_data.mbti
        )
        
        all_batch_requests = []
        qa_per_domain = total_qa_pairs // len(domains)
        
        # 도메인별로 QA 생성
        for domain_idx, domain in enumerate(domains):
            current_domain_qa = qa_per_domain
            
            # 마지막 도메인에는 나머지 QA 모두 할당
            if domain_idx == len(domains) - 1:
                current_domain_qa = total_qa_pairs - len(all_batch_requests)
            
            logger.info(f"도메인 '{domain}' QA 생성 시작: {current_domain_qa}개")
            
            for i in range(current_domain_qa):
                # 도메인별 특성 설명
                domain_descriptions = {
                    "일상생활": "일상의 소소한 일들, 취미, 습관, 음식, 주말 활동 등",
                    "과학기술": "AI, 기술 트렌드, 스마트폰, 미래 기술, 과학의 발전",
                    "사회이슈": "사회 문제, 환경, 불평등, 세대 간 차이, 미래 사회",
                    "인문학": "인생의 가치, 책, 예술, 철학, 역사의 교훈",
                    "스포츠": "운동, 건강관리, 스포츠 경기, 운동의 즐거움",
                    "역사문화": "전통문화, 역사적 장소, 문화의 다양성, 역사 인물"
                }
                
                domain_desc = domain_descriptions.get(domain, domain)
                
                # OpenAI Batch API 형식으로 변환
                custom_id = f"influencer_qa_{character_data.name}_{domain}_{i}"
                batch_request = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": system_prompt or f"당신은 {character_data.name}라는 인플루언서입니다. {character_data.personality} 성격을 가지고 있습니다."
                            },
                            {
                                "role": "user",
                                "content": f"""{domain}({domain_desc})에 관한 QA 쌍을 하나 만들어주세요.
{character_data.name}의 성격과 특성에 맞는 자연스럽고 흥미로운 질문을 만들고, 그에 대해 캐릭터답게 답변해주세요.
반드시 JSON 형식으로 답변해주세요:
{{"q": "질문 내용", "a": "답변 내용"}}"""
                            }
                        ],
                        "max_tokens": 500,
                        "temperature": 0.8,
                        "response_format": {"type": "json_object"}  # JSON 형식 강제
                    }
                }
                
                all_batch_requests.append(batch_request)
                task_entry["completed"] += 1
                task_entry["progress"] = (task_entry["completed"] / total_qa_pairs) * 100
                
                # 진행상황 로깅 (100개마다)
                if (i + 1) % 100 == 0:
                    logger.info(f"도메인 '{domain}' 진행: {i + 1}/{current_domain_qa}")
                    await asyncio.sleep(0.01)
        
        # 결과 저장
        task_entry["batch_requests"] = all_batch_requests
        task_entry["status"] = "completed"
        task_entry["progress"] = 100
        task_entry["end_time"] = datetime.now().isoformat()
        
        logger.info(f"인플루언서 QA 생성 완료: {task_id}, 총 {len(all_batch_requests)}개 생성")
        
    except Exception as e:
        task_entry["status"] = "failed"
        task_entry["error"] = str(e)
        task_entry["end_time"] = datetime.now().isoformat()
        logger.error(f"인플루언서 QA 생성 실패: {task_id}, 오류: {e}", exc_info=True)

# 하드코딩된 질문 생성 함수 제거 - OpenAI가 직접 질문과 답변 생성