"""
RunPod Serverless Worker for vLLM Generation with LoRA (최적화 버전)
사전 로딩 및 캐싱 전략으로 응답 속도 개선
"""
import os
import sys
import logging
import json
import torch
import traceback
from typing import Dict, Any, List, Optional, AsyncGenerator
import asyncio
import uuid
import time
from concurrent.futures import ThreadPoolExecutor
import threading

import runpod
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest
from transformers import AutoTokenizer
from huggingface_hub import snapshot_download

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 전역 변수
llm_engine = None
tokenizer = None
loaded_adapters = {}
adapter_load_times = {}  # 어댑터 로드 시간 추적
popular_adapters = []  # 인기 어댑터 목록
device = None

# 백그라운드 로더
background_loader = None
loading_queue = asyncio.Queue()

# 기본 설정
DEFAULT_MODEL = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
DEFAULT_SYSTEM_MESSAGE = "당신은 도움이 되는 AI 어시스턴트입니다."

# 환경 변수에서 사전 로드할 어댑터 목록 가져오기
PRELOAD_ADAPTERS = os.getenv("PRELOAD_ADAPTERS", "").split(",") if os.getenv("PRELOAD_ADAPTERS") else []
MAX_CACHED_ADAPTERS = int(os.getenv("MAX_CACHED_ADAPTERS", "10"))

def initialize_engine(model_name: str = DEFAULT_MODEL):
    """vLLM 엔진 초기화"""
    global llm_engine, tokenizer, device
    
    if llm_engine is not None:
        logger.info("엔진이 이미 초기화되어 있습니다.")
        return
    
    logger.info(f"🔧 vLLM 엔진 초기화 시작: {model_name}")
    
    # GPU 설정
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
        logger.info(f"🖥️ GPU 사용: {torch.cuda.get_device_name(0)}")
        logger.info(f"📊 GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        gpu_memory_utilization = 0.9
    else:
        device = torch.device("cpu")
        logger.warning("⚠️ CUDA를 사용할 수 없습니다. CPU를 사용합니다.")
        gpu_memory_utilization = 0
    
    try:
        # 토크나이저 로드
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # vLLM 엔진 초기화 (더 많은 LoRA 슬롯)
        llm_engine = LLM(
            model=model_name,
            tensor_parallel_size=1,
            trust_remote_code=True,
            dtype="bfloat16" if torch.cuda.is_available() else "float32",
            enable_lora=True,
            max_lora_rank=64,
            max_loras=10,  # 더 많은 LoRA 동시 로드
            gpu_memory_utilization=gpu_memory_utilization
        )
        
        logger.info("✅ vLLM 엔진 초기화 완료")
        
    except Exception as e:
        logger.error(f"❌ 엔진 초기화 실패: {str(e)}")
        raise

def preload_popular_adapters():
    """인기 어댑터 사전 로드"""
    logger.info("🔄 인기 어댑터 사전 로드 시작...")
    
    for adapter_path in PRELOAD_ADAPTERS:
        if not adapter_path:
            continue
            
        try:
            adapter_name = adapter_path.split("/")[-1]
            logger.info(f"📥 사전 로드 중: {adapter_name}")
            
            # 어댑터 로드
            load_lora_adapter(adapter_path, adapter_name)
            popular_adapters.append(adapter_name)
            
        except Exception as e:
            logger.error(f"❌ 어댑터 사전 로드 실패 {adapter_path}: {e}")
    
    logger.info(f"✅ {len(popular_adapters)}개 어댑터 사전 로드 완료")

def load_lora_adapter(adapter_path: str, adapter_name: str) -> Dict[str, Any]:
    """LoRA 어댑터 로드 (개선된 버전)"""
    global loaded_adapters, adapter_load_times
    
    # 이미 로드된 경우
    if adapter_name in loaded_adapters:
        logger.info(f"✅ 캐시에서 어댑터 사용: {adapter_name}")
        # 사용 시간 업데이트 (LRU 캐시용)
        adapter_load_times[adapter_name] = time.time()
        return loaded_adapters[adapter_name]
    
    # 캐시 크기 확인 및 정리
    if len(loaded_adapters) >= MAX_CACHED_ADAPTERS:
        # LRU 정책: 가장 오래 사용하지 않은 어댑터 제거
        oldest_adapter = min(adapter_load_times.items(), key=lambda x: x[1])[0]
        if oldest_adapter not in popular_adapters:  # 인기 어댑터는 제거하지 않음
            logger.info(f"🗑️ 캐시 정리: {oldest_adapter} 제거")
            del loaded_adapters[oldest_adapter]
            del adapter_load_times[oldest_adapter]
    
    start_time = time.time()
    
    try:
        # Hugging Face Hub에서 다운로드
        if adapter_path.startswith("hf://"):
            repo_id = adapter_path.replace("hf://", "")
            logger.info(f"📥 Hugging Face Hub에서 어댑터 다운로드: {repo_id}")
            local_path = snapshot_download(repo_id, cache_dir="/app/adapter_cache")
        else:
            local_path = adapter_path
        
        # LoRA 어댑터 정보 생성
        adapter_info = {
            "name": adapter_name,
            "path": local_path,
            "lora_int_id": len(loaded_adapters) + 1,
            "loaded_at": time.time()
        }
        
        loaded_adapters[adapter_name] = adapter_info
        adapter_load_times[adapter_name] = time.time()
        
        load_time = time.time() - start_time
        logger.info(f"✅ LoRA 어댑터 로드 완료: {adapter_name} ({load_time:.2f}초)")
        
        return adapter_info
        
    except Exception as e:
        logger.error(f"❌ LoRA 어댑터 로드 실패: {str(e)}")
        raise

async def background_adapter_loader():
    """백그라운드에서 어댑터 로드"""
    while True:
        try:
            adapter_info = await loading_queue.get()
            if adapter_info is None:  # 종료 신호
                break
                
            adapter_path = adapter_info["path"]
            adapter_name = adapter_info["name"]
            
            # 이미 로드 중이거나 로드된 경우 스킵
            if adapter_name not in loaded_adapters:
                logger.info(f"🔄 백그라운드 로드 시작: {adapter_name}")
                load_lora_adapter(adapter_path, adapter_name)
                
        except Exception as e:
            logger.error(f"백그라운드 로더 오류: {e}")

def predict_next_adapters(current_adapter: str) -> List[str]:
    """다음에 사용될 가능성이 높은 어댑터 예측"""
    # 실제로는 사용 패턴 분석을 통해 예측
    # 여기서는 간단한 예시
    predictions = []
    
    # 예: 특정 인플루언서 다음에 자주 사용되는 인플루언서
    adapter_sequences = {
        "influencer_a": ["influencer_b", "influencer_c"],
        "influencer_b": ["influencer_a", "influencer_d"],
        # ...
    }
    
    return adapter_sequences.get(current_adapter, [])

def handler(job):
    """RunPod 핸들러 함수 (최적화 버전)"""
    try:
        logger.info("📥 새로운 생성 요청 수신")
        
        # 엔진 초기화 확인
        if llm_engine is None:
            model_name = job["input"].get("model", DEFAULT_MODEL)
            initialize_engine(model_name)
            
            # 인기 어댑터 사전 로드
            preload_popular_adapters()
        
        # 입력 검증
        job_input = validate_input(job["input"])
        
        # LoRA 어댑터 처리
        lora_request = None
        adapter_name = None
        
        if job_input["lora_adapter"]:
            adapter_info = job_input["lora_adapter"]
            
            # 어댑터 로드
            if isinstance(adapter_info, dict):
                adapter_name = adapter_info.get("name", "custom_adapter")
                adapter_path = adapter_info["path"]
            else:
                adapter_path = adapter_info
                adapter_name = os.path.basename(adapter_path)
            
            # 로드 시간 측정
            load_start = time.time()
            loaded_adapter = load_lora_adapter(adapter_path, adapter_name)
            load_time = time.time() - load_start
            
            # LoRA Request 생성
            lora_request = LoRARequest(
                lora_name=adapter_name,
                lora_int_id=loaded_adapter["lora_int_id"],
                lora_path=loaded_adapter["path"]
            )
            
            logger.info(f"🔧 LoRA 어댑터 준비 완료: {adapter_name} ({load_time:.2f}초)")
            
            # 다음 어댑터 예측 및 백그라운드 로드
            next_adapters = predict_next_adapters(adapter_name)
            for next_adapter in next_adapters:
                if next_adapter not in loaded_adapters:
                    asyncio.create_task(loading_queue.put({
                        "name": next_adapter,
                        "path": f"hf://username/{next_adapter}"
                    }))
        
        # 샘플링 파라미터 설정
        sampling_params = SamplingParams(
            temperature=job_input["temperature"],
            max_tokens=job_input["max_tokens"],
            top_p=job_input["top_p"],
            top_k=job_input["top_k"],
            repetition_penalty=job_input["repetition_penalty"],
            stop=job_input["stop_sequences"],
            n=job_input["n"]
        )
        
        # 텍스트 생성
        logger.info("🚀 텍스트 생성 시작...")
        gen_start = time.time()
        
        results = generate_text(
            prompt=job_input["prompt"],
            sampling_params=sampling_params,
            lora_request=lora_request
        )
        
        gen_time = time.time() - gen_start
        
        # 응답 정리
        cleaned_results = [
            clean_response(result, job_input["influencer_name"])
            for result in results
        ]
        
        # 결과 생성
        result = {
            "status": "success",
            "generated_text": cleaned_results[0] if len(cleaned_results) == 1 else cleaned_results,
            "model": DEFAULT_MODEL,
            "used_lora": job_input["lora_adapter"] is not None,
            "temperature": job_input["temperature"],
            "max_tokens": job_input["max_tokens"],
            "num_generated": len(cleaned_results),
            "performance": {
                "adapter_load_time": load_time if job_input["lora_adapter"] else 0,
                "generation_time": gen_time,
                "total_time": time.time() - logger.info("📥 새로운 생성 요청 수신")
            }
        }
        
        if job_input["lora_adapter"]:
            result["lora_adapter"] = adapter_name
            result["cached"] = load_time < 0.1  # 0.1초 미만이면 캐시에서 로드
        
        logger.info(f"✅ 텍스트 생성 완료 (총 {result['performance']['total_time']:.2f}초)")
        return result
        
    except Exception as e:
        error_msg = f"생성 처리 중 오류 발생: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(traceback.format_exc())
        
        return {
            "status": "failed",
            "error": error_msg,
            "traceback": traceback.format_exc()
        }

# 기존 함수들은 동일...
def validate_input(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """입력 데이터 검증"""
    # 기존 코드와 동일
    pass

def generate_text(prompt: str, sampling_params: SamplingParams, lora_request: Optional[LoRARequest] = None) -> List[str]:
    """텍스트 생성"""
    # 기존 코드와 동일
    pass

def clean_response(response: str, influencer_name: Optional[str] = None) -> str:
    """응답 정리"""
    # 기존 코드와 동일
    pass

def create_chat_prompt(user_message: str, system_message: str = DEFAULT_SYSTEM_MESSAGE, influencer_name: Optional[str] = None, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
    """채팅 프롬프트 생성"""
    # 기존 코드와 동일
    pass

# RunPod 서버리스 실행
if __name__ == "__main__":
    logger.info("🚀 RunPod vLLM Generation Worker 시작 (최적화 버전)")
    logger.info(f"📋 기본 모델: {DEFAULT_MODEL}")
    logger.info(f"📦 사전 로드 어댑터: {PRELOAD_ADAPTERS}")
    logger.info(f"💾 최대 캐시 어댑터: {MAX_CACHED_ADAPTERS}")
    
    # 백그라운드 로더 시작
    asyncio.create_task(background_adapter_loader())
    
    runpod.serverless.start({
        "handler": handler
    })