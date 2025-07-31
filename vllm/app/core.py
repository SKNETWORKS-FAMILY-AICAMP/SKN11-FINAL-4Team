import os
# vLLM 설정
os.environ["VLLM_USE_V1"] = "0" # vLLM v1 어텐션 백엔드 비활성화
os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"  # 멀티프로세스 방식 변경

# GPU 설정은 각 프로세스에서 개별적으로 처리
# 메인 프로세스에서는 CUDA_VISIBLE_DEVICES를 설정하지 않음
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
# embedding_model 전역 변수 제거 - 멀티프로세싱으로 처리
loaded_adapters: Dict[str, Dict[str, Any]] = {}
finetuning_tasks: Dict[str, Dict[str, Any]] = {}  # 파인튜닝 작업 저장
finetuning_queue: asyncio.Queue = None # 파인튜닝 작업을 위한 큐

# 환경 변수
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FINETUNING_POST_URL = os.getenv("FINETUNING_POST_URL")  # 새로운 POST URL

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

async def send_finetuning_result(task_id: str, status: str, hf_model_url: Optional[str] = None, error_message: Optional[str] = None):
    """파인튜닝 완료/실패 시 백엔드 서버로 결과 전송"""
    # POST URL 사용
    post_url = FINETUNING_POST_URL
    
    if not post_url:
        logger.warning("⚠️ FINETUNING_POST_URL이 설정되지 않아 결과를 전송하지 않습니다.")
        return

    task = finetuning_tasks.get(task_id)
    if not task:
        logger.error(f"결과 전송 실패: 작업 {task_id}를 찾을 수 없습니다.")
        return

    # POST 방식으로 변경된 페이로드
    payload = {
        "task_id": task_id,
        "influencer_id": task["influencer_id"],
        "status": status,
        "hf_model_url": hf_model_url,
        "error_message": error_message,
        "metadata": {
            "training_epochs": task.get("training_epochs"),
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
            "qa_data_count": len(task.get("qa_data", [])),
            "hf_repo_id": task.get("hf_repo_id")
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(post_url, json=payload, timeout=30.0)
            response.raise_for_status()
            logger.info(f"✅ 파인튜닝 결과 전송 성공: {task_id}, 상태: {status}, 응답: {response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"❌ 파인튜닝 결과 전송 실패 (RequestError): {task_id}, {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ 파인튜닝 결과 전송 실패 (HTTPStatusError): {task_id}, 상태 코드: {e.response.status_code}, 응답: {e.response.text}")
    except Exception as e:
        logger.error(f"❌ 파인튜닝 결과 전송 중 알 수 없는 오류: {task_id}, {e}")

async def run_finetuning_pipeline(qa_data: List[Dict], system_message: str, 
                                hf_token: str, hf_repo_id: str, training_epochs: int) -> Optional[str]:
    """파인튜닝 파이프라인 직접 실행"""
    try:
        logger.info(f"🔄 파인튜닝 파이프라인 실행: {hf_repo_id}")
        logger.info(f"🔍 파이프라인 QA 데이터: 개수={len(qa_data)}")
        
        # GPU 메모리 체크
        import torch
        if torch.cuda.is_available():
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"🖥️ GPU 메모리: {gpu_mem:.2f}GB")
            if gpu_mem < 16:  # 16GB 미만이면 경고
                logger.warning(f"⚠️ GPU 메모리가 부족할 수 있습니다 ({gpu_mem:.2f}GB < 16GB)")
        
        # 멀티프로세싱 사용 여부 확인 (기본값: true)
        use_multiprocessing = os.getenv('USE_FINETUNING_MULTIPROCESSING', 'true').lower() == 'true'
        
        if use_multiprocessing:
            # 멀티프로세싱 방식 (완전 격리)
            logger.info("🔄 파인튜닝을 멀티프로세싱으로 실행 (완전 격리)")
            from app.routers.finetuning_async import submit_finetuning_task
            
            task_data = {
                'task_id': f"ft_{hf_repo_id}_{int(time.time())}",
                'qa_data': qa_data,
                'system_message': system_message,
                'hf_token': hf_token,
                'hf_repo_id': hf_repo_id,
                'training_epochs': training_epochs
            }
            
            response = await submit_finetuning_task(task_data)
            
            if response['status'] == 'success':
                return response['hf_model_url']
            else:
                error_msg = response.get('error', '파인튜닝 실패')
                if 'out of memory' in error_msg.lower():
                    logger.error(f"❌ GPU 메모리 부족: {error_msg}")
                    logger.info("💡 해결 방법: batch_size 감소, LoRA rank 감소, 또는 더 큰 GPU 사용")
                raise Exception(error_msg)
        else:
            # 스레드 방식 (가벼운 격리)
            logger.info("🧵 파인튜닝을 별도 스레드에서 실행 (비블로킹)")
            from pipeline import fine_custom
            
            hf_model_url = await asyncio.to_thread(
                fine_custom.main,
                qa_data=qa_data,
                system_message=system_message,
                hf_token=hf_token,
                hf_repo_id=hf_repo_id,
                training_epochs=training_epochs
            )
            
            return hf_model_url
        
        logger.info(f"✅ 파인튜닝 파이프라인 실행 완료: {hf_repo_id}")
            
    except RuntimeError as e:
        if "out of memory" in str(e) or "CUDA out of memory" in str(e):
            logger.error(f"❌ GPU 메모리 부족 오류: {e}")
            logger.info("💡 다음을 시도해보세요:")
            logger.info("  1. batch_size를 1로 줄이기")
            logger.info("  2. gradient_accumulation_steps 늘리기")
            logger.info("  3. LoRA rank를 4 이하로 줄이기")
            logger.info("  4. max_length를 512로 줄이기")
        raise e
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
        # 파인튜닝 완료/실패 시 결과 전송
        await send_finetuning_result(
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

async def restart_engine():
    """엔진을 재시작합니다."""
    global engine, tokenizer
    logger.info("🔄 엔진 재시작 시작...")
    
    # GPU 설정은 vLLM 엔진 초기화 시 처리
    logger.info("🖥️ vLLM은 엔진 초기화 시 GPU를 자동 선택합니다")
    
    # 기존 엔진 종료
    if engine is not None:
        try:
            logger.info("⏹️ 기존 엔진 종료 중...")
            # 엔진 종료 로직
            engine = None
            
            # GPU 메모리 정리
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            logger.info("✅ 기존 엔진 종료 및 메모리 정리 완료")
        except Exception as e:
            logger.error(f"❌ 엔진 종료 중 오류: {e}")
    
    # 새 엔진 초기화
    await initialize_vllm_engine()
    logger.info("✅ 엔진 재시작 완료")

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
        
            # GPU 설정 및 격리 확인
            vllm_gpu_id = int(os.getenv('VLLM_GPU_ID', '0'))
            
            # vLLM 전용 GPU 설정 (격리하지 않고 tensor_parallel_size로 제어)
            logger.info(f"🔧 vLLM이 GPU {vllm_gpu_id}를 사용하도록 설정")
            logger.info(f"📍 다른 서비스는 멀티프로세싱으로 개별 GPU 할당됨")
        
            # GPU 메모리 fraction 설정
            gpu_memory_fraction = float(os.getenv('VLLM_GPU_MEMORY_UTILIZATION', '0.5'))
            logger.info(f"💾 GPU 메모리 사용률: {gpu_memory_fraction * 100}%")
            
            # CUDA 디바이스 설정 확인 및 충돌 방지
            import torch
            if torch.cuda.is_available():
                # 다른 프로세스와의 충돌 방지를 위해 초기화
                torch.cuda.empty_cache()
                
                # 격리된 환경에서는 항상 device 0 사용
                if 'CUDA_VISIBLE_DEVICES' in os.environ:
                    cuda_device = 0
                else:
                    cuda_device = vllm_gpu_id
                    
                try:
                    torch.cuda.set_device(cuda_device)
                    logger.info(f"🖥️ CUDA 디바이스 설정 완료: {cuda_device}")
                except RuntimeError as e:
                    logger.warning(f"⚠️ CUDA 디바이스 설정 실패: {e}")
                    logger.info("🔄 기본 디바이스 사용")
            
            engine_args = AsyncEngineArgs(
                model="LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct",
                max_model_len=2048,
                tensor_parallel_size=1,  # 단일 GPU 사용 명시
                pipeline_parallel_size=1,  # 파이프라인 병렬화 비활성화
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
                enforce_eager=True,  # CUDA 그래프 비활성화로 디바이스 문제 방지
                device=f"cuda:{vllm_gpu_id}",  # 환경변수에 따라 GPU 지정
                disable_custom_all_reduce=True,  # 다중 GPU 통신 비활성화
            )
            
            engine = AsyncLLMEngine.from_engine_args(engine_args)
            logger.info("✅ vLLM LoRA 엔진 초기화 완료 (FastAPI 내부 엔진 모드)!")
        except Exception as vllm_error:
            logger.warning(f"⚠️ vLLM 엔진 초기화 실패 (GPU 없음?): {vllm_error}")
            logger.info("📝 vLLM 엔진 없이 파인튜닝과 Speech Generator만 사용 가능합니다")
        
    except Exception as e:
        logger.error(f"❌ 초기화 실패: {e}")
        raise e


# 임베딩 모델 초기화는 멀티프로세싱 워커에서 처리
# async def initialize_embedding_model():
#     """임베딩 모델 초기화 - DEPRECATED: embedding.py의 멀티프로세싱으로 이동"""
#     pass


# get_device 함수는 제거됨 - 각 프로세스에서 독립적으로 GPU 설정


# get_embedding_model 함수는 제거됨 - 멀티프로세싱 Queue를 통해 통신


async def startup_event():
    """서버 시작 시 비동기 엔진 초기화 및 파인튜닝 워커 시작"""
    global finetuning_queue
    
    try:
        await initialize_vllm_engine()
        logger.info("✅ vLLM 엔진 초기화 완료")
    except Exception as e:
        logger.error(f"❌ vLLM 엔진 초기화 실패: {e}")
        logger.warning("⚠️ vLLM 엔진 없이 파인튜닝 큐만 초기화합니다")

    # 임베딩 모델은 멀티프로세싱으로 별도 초기화
    logger.info("📌 임베딩 모델은 멀티프로세싱 워커에서 GPU 1번으로 초기화됩니다")

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
        
        # CUDA 디바이스 확인 및 설정
        import torch
        if torch.cuda.is_available():
            torch.cuda.set_device(0)
            logger.info(f"🖥️ LoRA 어댑터 로드 시 CUDA 디바이스 0 사용 설정")
        
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