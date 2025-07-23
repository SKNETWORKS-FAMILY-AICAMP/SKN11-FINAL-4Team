import os
os.environ["VLLM_USE_V1"] = "0" # vLLM v1 어텐션 백엔드 비활성화
import asyncio
import logging
import time
from typing import Optional, Dict, Any, List

import httpx
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.engine.async_llm_engine import AsyncLLMEngine
from huggingface_hub import login

from app.models import FineTuningStatus, LoRALoadRequest
from pipeline.speech_generator import SpeechGenerator
from app.utils.adapter_utils import get_base_model_from_adapter
from app.utils.finetuning_utils import create_system_message, convert_qa_data_for_finetuning
from app.utils.cache_manager import get_cache_manager
# GPU manager removed - using device_map='auto' instead
from pipeline import fine_custom
import dotenv
import re

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

async def get_available_gpu_memory_mb(device_id: int = 0) -> int:
    """GPU 메모리 체크를 건너뜁니다 (device_map='auto' 사용)."""
    # device_map='auto'를 사용하므로 메모리 체크 불필요
    return 10240  # 충분한 메모리가 있다고 가정 (10GB)


from fastapi import HTTPException

# 전역 변수
engine: AsyncLLMEngine = None
tokenizer = None  # 토크나이저 전역 변수 추가
loaded_adapters: Dict[str, Dict[str, Any]] = {}
finetuning_tasks: Dict[str, Dict[str, Any]] = {}  # 파인튜닝 작업 저장
finetuning_queue: asyncio.Queue = None # 파인튜닝 작업을 위한 큐

# 환경 변수
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FINETUNING_WEBHOOK_URL = os.getenv("FINETUNING_WEBHOOK_URL")

def get_speech_generator() -> SpeechGenerator:
    """
    SpeechGenerator 인스턴스를 생성하고 반환하는 의존성 주입 함수.
    OPENAI_API_KEY가 설정되지 않은 경우 HTTPException을 발생시킵니다.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ Speech Generator를 초기화할 수 없습니다. OPENAI_API_KEY가 설정되지 않았습니다.")
        raise HTTPException(
            status_code=503,
            detail="Speech Generator is not available due to missing OPENAI_API_KEY."
        )
    logger.info("✅ SpeechGenerator 인스턴스 생성 (for OpenAI API)")
    return SpeechGenerator(api_key=api_key)
FINETUNING_WEBHOOK_URL = os.getenv("FINETUNING_WEBHOOK_URL")

async def send_finetuning_webhook(task_id: str, status: str, hf_model_url: Optional[str] = None, error_message: Optional[str] = None):
    """파인튜닝 완료/실패 시 백엔드 서버로 웹훅 전송"""
    if not FINETUNING_WEBHOOK_URL:
        logger.warning("⚠️ FINETUNING_WEBHOOK_URL이 설정되지 않아 웹훅을 전송하지 않습니다.")
        return

    task = finetuning_tasks.get(task_id)
    if not task:
        logger.error(f"웹훅 전송 실패: 작업 {task_id}를 찾을 수 없습니다.")
        return

    payload = {
        "task_id": task_id,
        "influencer_id": task["influencer_id"],
        "status": status,
        "hf_model_url": hf_model_url,
        "error_message": error_message
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(FINETUNING_WEBHOOK_URL, json=payload, timeout=30.0)
            response.raise_for_status()
            logger.info(f"✅ 파인튜닝 웹훅 전송 성공: {task_id}, 상태: {status}, 응답: {response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"❌ 파인튜닝 웹훅 전송 실패 (RequestError): {task_id}, {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ 파인튜닝 웹훅 전송 실패 (HTTPStatusError): {task_id}, 상태 코드: {e.response.status_code}, 응답: {e.response.text}")
    except Exception as e:
        logger.error(f"❌ 파인튜닝 웹훅 전송 중 알 수 없는 오류: {task_id}, {e}")

async def run_finetuning_pipeline(qa_data: List[Dict], system_message: str, 
                                hf_token: str, hf_repo_id: str, training_epochs: int) -> Optional[str]:
    """파인튜닝 파이프라인 직접 실행"""
    try:
        logger.info(f"🔄 파인튜닝 파이프라인 실행: {hf_repo_id}")
        logger.info(f"🔍 파이프라인 QA 데이터: 개수={len(qa_data)}")
        logger.info(f"🎯 device_map='auto'로 자동 GPU 할당")
        
        # fine_custom 모듈을 동적으로 import
        from pipeline import fine_custom
        
        # 직접 fine_custom.main 함수 호출
        hf_model_url = fine_custom.main(
            qa_data=qa_data,
            system_message=system_message,
            hf_token=hf_token,
            hf_repo_id=hf_repo_id,
            training_epochs=training_epochs
        )
        
        logger.info(f"✅ 파인튜닝 파이프라인 실행 완료: {hf_repo_id}")
        return hf_model_url
            
    except Exception as e:
        logger.error(f"❌ 파인튜닝 파이프라인 실행 실패: {e}")
        raise e

async def execute_finetuning(task_id: str):
    """파인튜닝 실행 (백그라운드 작업)"""
    task = finetuning_tasks.get(task_id)
    if not task:
        return
    
    hf_model_url = None
    error_message = None

    try:
        logger.info(f"🎯 파인튜닝 실행 시작: {task_id}")
        
        # device_map='auto'를 사용하므로 GPU 선택 로직 제거
        logger.info("🖥️ device_map='auto'로 GPU 자동 할당")
        selected_gpu = None  # device_map='auto' 사용
        
        # 1. 데이터 준비 단계
        task["status"] = FineTuningStatus.PREPARING_DATA.value
        task["updated_at"] = time.time()
        
        # 시스템 메시지 생성
        system_message = task["system_prompt"]
        print(system_message)
        # QA 데이터 형식 확인 및 변환
        qa_data = task["qa_data"]
        is_converted = task.get("is_converted", False)
        
        logger.info(f"🔍 QA 데이터 디버깅: 개수={len(qa_data) if qa_data else 0}, is_converted={is_converted}")
        if qa_data:
            logger.info(f"🔍 첫 번째 QA 데이터 샘플: {qa_data[0]}")
        
        # 이미 변환된 데이터인지 확인
        if is_converted or (qa_data and isinstance(qa_data[0], dict) and "messages" in qa_data[0]):
            logger.info("이미 변환된 파인튜닝 데이터 사용")
            finetuning_data = qa_data
        else:
            logger.info("QA 데이터를 파인튜닝용 형식으로 변환")
            try:
                finetuning_data = convert_qa_data_for_finetuning(
                    qa_data, 
                    task["influencer_name"],
                    task["personality"],
                    task["style_info"]
                )
            except Exception as e:
                logger.error(f"❌ QA 데이터 변환 중 오류: {e}")
                logger.error(f"❌ QA 데이터 샘플: {qa_data[:3] if qa_data else 'None'}")
                raise
        
        # 2. 파인튜닝 실행
        task["status"] = FineTuningStatus.TRAINING.value
        task["updated_at"] = time.time()
        
        logger.info(f"🔧 파인튜닝에 device_map='auto' 사용 (자동 할당)")
        
        try:
            hf_model_url = await run_finetuning_pipeline(
                qa_data=finetuning_data,
                system_message=system_message,
                hf_token=task["hf_token"],
                hf_repo_id=task["hf_repo_id"],
                training_epochs=task["training_epochs"]
            )
            
            if hf_model_url:
                # 3. 완료
                task["status"] = FineTuningStatus.COMPLETED.value
                task["hf_model_url"] = hf_model_url
                task["updated_at"] = time.time()
                
                logger.info(f"✅ 파인튜닝 완료: {task_id} → {hf_model_url}")
                
                # 완료된 모델을 자동으로 로드
                try:
                    load_request = LoRALoadRequest(
                        model_id=task["hf_repo_id"],
                        hf_repo_name=task["hf_repo_id"],
                        hf_token=task["hf_token"]
                    )
                    await load_lora_adapter(load_request)
                    logger.info(f"🔄 파인튜닝 완료 후 어댑터 자동 로드: {task['hf_repo_id']}")
                except Exception as e:
                    logger.warning(f"⚠️ 파인튜닝 완료 후 어댑터 자동 로드 실패: {e}")
            else:
                raise Exception("파인튜닝 실행 실패: 모델 URL을 반환하지 못했습니다.")
                
        finally:
            # GPU 메모리 정리
            logger.info(f"🧹 GPU 메모리 정리 중...")
            
    except Exception as e:
        task["status"] = FineTuningStatus.FAILED.value
        task["error_message"] = str(e)
        task["updated_at"] = time.time()
        logger.error(f"❌ 파인튜닝 실패: {task_id}, {e}")
        error_message = str(e)
    finally:
        # 파인튜닝 완료/실패 시 웹훅 전송
        await send_finetuning_webhook(
            task_id=task_id,
            status=task["status"],
            hf_model_url=hf_model_url,
            error_message=error_message
        )

async def finetuning_worker():
    """파인튜닝 작업을 큐에서 가져와 처리하는 워커"""
    MIN_GPU_MEMORY_MB = 1024 * 10

    while True:
        task_id = await finetuning_queue.get()
        logger.info(f"⚙️ 큐에서 파인튜닝 작업 시작: {task_id}")
        
        # device_map='auto'를 사용하므로 GPU 선택 로직 제거
        logger.info("🖥️ device_map='auto'로 GPU 자동 할당")
        available_memory = await get_available_gpu_memory_mb()
        logger.info(f"GPU 메모리 확인: {available_memory}MB")
        if available_memory != -1 and available_memory < MIN_GPU_MEMORY_MB:
            logger.warning(f"⚠️ GPU 메모리 부족 ({available_memory}MB). 최소 {MIN_GPU_MEMORY_MB}MB 필요. 작업 {task_id}를 다시 큐에 넣습니다.")
            await finetuning_queue.put(task_id) 
            finetuning_queue.task_done()
            await asyncio.sleep(60) 
            continue

        try:
            await execute_finetuning(task_id)
        except Exception as e:
            logger.error(f"❌ 파인튜닝 워커 오류: {task_id}, {e}")
        finally:
            # 작업 완료 후 GPU 메모리 정리
            try:
                import gc
                gc.collect()
                
                # PyTorch로 직접 GPU 메모리 정리
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                logger.info(f"♾️ 파인튜닝 작업 {task_id} 후 GPU 메모리 정리 완료")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ GPU 메모리 정리 실패: {cleanup_error}")
            
            finetuning_queue.task_done()

async def initialize_vllm_engine():
    global engine, tokenizer
    logger.info("🚀 vLLM LoRA 엔진 초기화 중...")
    
    try:
        # 토크나이저 초기화 (chat template 사용을 위해)
        try:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct",
                trust_remote_code=True
            )
            logger.info("✅ 토크나이저 초기화 완료")
        except Exception as tokenizer_error:
            logger.warning(f"⚠️ 토크나이저 초기화 실패: {tokenizer_error}")
        
        # vLLM 엔진 초기화 (GPU 필요하므로 실패할 수 있음)
        try:
            tensor_parallel_size = 1
        
            # vLLM은 자동으로 GPU 할당 (보통 0번 GPU 사용)
            logger.info(f"vLLM GPU 자동 할당 모드")
        
            # GPU 메모리 fraction을 고정값으로 설정
            gpu_memory_fraction = 0.5
            
            engine_args = AsyncEngineArgs(
                model="LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct",
                max_model_len=2048,
                tensor_parallel_size=tensor_parallel_size,
                trust_remote_code=True,
                gpu_memory_utilization=gpu_memory_fraction,
                enable_lora=True,
                max_loras=8,
                max_lora_rank=64,
                lora_extra_vocab_size=256,
                max_cpu_loras=16,
                max_num_seqs=256,
                max_num_batched_tokens=8192,
                disable_log_requests=True,
            )
            
            engine = AsyncLLMEngine.from_engine_args(engine_args)
            logger.info("✅ vLLM LoRA 엔진 초기화 완료 (FastAPI 내부 엔진 모드)!")
        except Exception as vllm_error:
            logger.warning(f"⚠️ vLLM 엔진 초기화 실패 (GPU 없음?): {vllm_error}")
            logger.info("📝 vLLM 엔진 없이 파인튜닝과 Speech Generator만 사용 가능합니다")
        
    except Exception as e:
        logger.error(f"❌ 초기화 실패: {e}")
        raise e

async def startup_event():
    """서버 시작 시 비동기 엔진 초기화 및 파인튜닝 워커 시작"""
    global finetuning_queue
    
    try:
        await initialize_vllm_engine()
        logger.info("✅ vLLM 엔진 초기화 완료")
    except Exception as e:
        logger.error(f"❌ vLLM 엔진 초기화 실패: {e}")
        logger.warning("⚠️ vLLM 엔진 없이 파인튜닝 큐만 초기화합니다")

    # vLLM 엔진 초기화 실패와 관계없이 파인튜닝 큐는 초기화
    logger.info("🔄 파인튜닝 큐 초기화 중...")
    finetuning_queue = asyncio.Queue()
    logger.info(f"✅ 파인튜닝 큐 초기화 완료: {finetuning_queue}")
    
    logger.info("🔄 파인튜닝 워커 시작 중...")
    asyncio.create_task(finetuning_worker())
    logger.info("✅ 파인튜닝 워커 시작됨")
    
    logger.info(f"🔍 최종 확인 - finetuning_queue: {finetuning_queue}")

async def load_lora_adapter(request: LoRALoadRequest):
    """LoRA 어댑터 로드"""
    if engine is None:
        raise Exception("엔진이 초기화되지 않았습니다.")
    
    try:
        logger.info(f"🔄 LoRA 어댑터 로딩 요청 받음: model_id={request.model_id}, repo={request.hf_repo_name}")
        
        if request.model_id in loaded_adapters:
            logger.info(f"♻️ 어댑터 {request.model_id}는 이미 로드되어 있습니다.")
            return {
                "message": f"어댑터 {request.model_id}는 이미 로드되어 있습니다.",
                "adapter_info": loaded_adapters[request.model_id]
            }
        
        logger.info(f"🔄 LoRA 어댑터 로딩 시작: {request.hf_repo_name}")
        
        if request.hf_token:
            try:
                logger.info("🔑 허깅페이스 토큰 로그인 시도 중...")
                login(token=request.hf_token)
                logger.info("🔑 허깅페이스 토큰 로그인 성공")
            except Exception as e:
                logger.warning(f"⚠️ 허깅페이스 로그인 실패: {e}")
                # 토큰 로그인 실패해도 계속 진행
        else:
            logger.info("ℹ️ HuggingFace 토큰이 제공되지 않았습니다.")
        
        logger.info("📋 베이스 모델 정보 확인 중...")
        try:
            base_model_name = (
                request.base_model_override or 
                get_base_model_from_adapter(request.hf_repo_name, request.hf_token)
            )
            logger.info(f"📋 베이스 모델 확인 완료: {base_model_name}")
        except Exception as e:
            logger.error(f"❌ 베이스 모델 정보 확인 실패: {e}")
            raise Exception(f"베이스 모델 정보 확인 실패: {str(e)}")
        
        logger.info("📦 어댑터 정보 객체 생성 중...")
        adapter_info = {
            "model_id": request.model_id,
            "hf_repo_name": request.hf_repo_name,
            "base_model_name": base_model_name,
            "status": "loaded",
            "lora_int_id": hash(request.model_id) % 1000000
        }
        logger.info(f"📦 생성된 어댑터 정보: {adapter_info}")
        
        logger.info("💾 로드된 어댑터 목록에 추가 중...")
        loaded_adapters[request.model_id] = adapter_info
        logger.info(f"💾 현재 로드된 어댑터 목록: {list(loaded_adapters.keys())}")
        
        logger.info(f"✅ LoRA 어댑터 로드 완료: {request.model_id}")
        
        result = {
            "message": f"LoRA 어댑터 {request.model_id} 로드 완료",
            "adapter_info": adapter_info
        }
        logger.info(f"📤 반환할 결과: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ LoRA 어댑터 로드 실패: {e}")
        raise Exception(f"어댑터 로드 실패: {str(e)}")