"""
RunPod Serverless Worker for vLLM Generation
베이스 모델을 미리 로드하고 HuggingFace의 LoRA 어댑터를 동적으로 로드하여 텍스트 생성
"""
import os
import logging
import json
import traceback
from typing import Dict, Any, Optional, AsyncIterator
import uuid
import time
import asyncio

import runpod
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest
from transformers import AutoTokenizer
from huggingface_hub import snapshot_download

# GPU 메모리 모니터링을 위한 라이브러리
try:
    import torch
    GPU_MONITORING_AVAILABLE = True
except ImportError:
    GPU_MONITORING_AVAILABLE = False
    logger.warning("⚠️ PyTorch 미설치 - GPU 메모리 모니터링 비활성화")

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 전역 변수 및 엔진 상태 관리
llm_engine = None
tokenizer = None
loaded_adapters = {}
_engine_initialized = False

# 기본 설정
DEFAULT_MODEL = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
DEFAULT_SYSTEM_MESSAGE = "당신은 도움이 되는 AI 어시스턴트입니다."
PRELOAD_MODEL = os.environ.get("PRELOAD_MODEL", "true").lower() == "true"


def initialize_engine(model_name: str = DEFAULT_MODEL):
    """vLLM 엔진 초기화 (동기, 싱글톤 패턴)"""
    global llm_engine, tokenizer, _engine_initialized
    
    # 이미 초기화된 경우 반환 (엔진 객체만 확인)
    if llm_engine is not None:
        logger.info("✅ 엔진이 이미 초기화되어 있습니다.")
        return llm_engine
    
    logger.info(f"🔧 vLLM 엔진 초기화 시작: {model_name}")
    
    try:
        # 토크나이저 로드
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # vLLM 엔진 초기화
        llm_engine = LLM(
            model=model_name,
            trust_remote_code=True,
            dtype="bfloat16",
            enable_lora=True,
            max_lora_rank=64,
            max_loras=10,
            gpu_memory_utilization=0.2,  # GPU 메모리 사용률 조정 (10GB 가용시 약 9.5GB 사용)
            max_model_len=4096,
            enforce_eager=True,  # 메모리 안정성 향상
        )
        
        _engine_initialized = True
        logger.info("✅ vLLM 엔진 초기화 완료")
        log_gpu_memory()  # 초기화 후 메모리 상태 로그
        return llm_engine
        
    except Exception as e:
        logger.error(f"❌ 엔진 초기화 실패: {str(e)}")
        _engine_initialized = False
        raise


def create_chat_prompt(
    user_message: str,
    system_message: str = DEFAULT_SYSTEM_MESSAGE,
    chat_history: Optional[list] = None
) -> str:
    """채팅 프롬프트 생성"""
    messages = []
    
    # 시스템 메시지
    messages.append({"role": "system", "content": system_message})
    
    # 채팅 히스토리 추가
    if chat_history:
        messages.extend(chat_history)
    
    # 사용자 메시지
    messages.append({"role": "user", "content": user_message})
    
    # 토크나이저의 chat template 적용
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    return prompt


def download_lora_adapter(hf_repo: str, hf_token: Optional[str] = None) -> str:
    """HuggingFace에서 LoRA 어댑터 다운로드"""
    try:
        logger.info(f"📥 HuggingFace에서 LoRA 어댑터 다운로드: {hf_repo}")
        
        # 캐시 디렉토리
        cache_dir = "/app/lora_cache"
        os.makedirs(cache_dir, exist_ok=True)
        
        # 다운로드 옵션
        download_kwargs = {
            "repo_id": hf_repo,
            "cache_dir": cache_dir,
        }
        
        if hf_token:
            download_kwargs["token"] = hf_token
            logger.info("🔑 HuggingFace 토큰 사용")
        
        # 스냅샷 다운로드
        local_path = snapshot_download(**download_kwargs)
        
        logger.info(f"✅ LoRA 어댑터 다운로드 완료: {local_path}")
        return local_path
        
    except Exception as e:
        logger.error(f"❌ LoRA 어댑터 다운로드 실패: {e}")
        raise


def load_lora_adapter(hf_repo: str, hf_token: Optional[str] = None) -> Dict[str, Any]:
    """LoRA 어댑터 로드"""
    global loaded_adapters
    
    # 캐시 확인
    if hf_repo in loaded_adapters:
        logger.info(f"✅ 캐시된 어댑터 사용: {hf_repo}")
        return loaded_adapters[hf_repo]
    
    try:
        # HuggingFace에서 다운로드
        local_path = download_lora_adapter(hf_repo, hf_token)
        
        # 어댑터 정보 생성
        adapter_info = {
            "name": hf_repo,
            "path": local_path,
            "lora_int_id": len(loaded_adapters) + 1,
        }
        
        # 캐시 저장
        loaded_adapters[hf_repo] = adapter_info
        logger.info(f"✅ LoRA 어댑터 로드 완료: {hf_repo}")
        
        return adapter_info
        
    except Exception as e:
        logger.error(f"❌ LoRA 어댑터 로드 실패: {e}")
        raise


def validate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """페이로드 검증 및 정규화"""
    # 필수 필드 확인
    required_fields = ["hf_token", "hf_repo", "system_message", "prompt"]
    for field in required_fields:
        if field not in payload or not payload[field]:
            raise ValueError(f"필수 필드 누락: {field}")
    
    # 입력 정규화
    validated = {
        "hf_token": payload["hf_token"],
        "hf_repo": payload["hf_repo"],
        "system_message": payload["system_message"],
        "prompt": payload["prompt"],
        "temperature": float(payload.get("temperature", 0.7)),
        "max_tokens": int(payload.get("max_tokens", 512)),
        "top_p": float(payload.get("top_p", 0.9)),
        "top_k": int(payload.get("top_k", 50)),
        "repetition_penalty": float(payload.get("repetition_penalty", 1.1)),
    }
    
    return validated


def generate_response(payload: Dict[str, Any]) -> str:
    """텍스트 생성 (동기)"""
    try:
        # 페이로드 검증
        validated = validate_payload(payload)
        
        # LoRA 어댑터 로드
        adapter_info = load_lora_adapter(validated["hf_repo"], validated["hf_token"])
        lora_request = LoRARequest(
            lora_name=adapter_info["name"],
            lora_int_id=adapter_info["lora_int_id"],
            lora_path=adapter_info["path"]
        )
        
        # 프롬프트 생성
        prompt = create_chat_prompt(
            user_message=validated["prompt"],
            system_message=validated["system_message"]
        )
        
        # 샘플링 파라미터
        sampling_params = SamplingParams(
            temperature=validated["temperature"],
            max_tokens=validated["max_tokens"],
            top_p=validated["top_p"],
            top_k=validated["top_k"],
            repetition_penalty=validated["repetition_penalty"],
        )
        
        # 텍스트 생성
        logger.info(f"🚀 텍스트 생성 시작 - LoRA: {validated['hf_repo']}")
        outputs = llm_engine.generate(
            prompts=[prompt],
            sampling_params=sampling_params,
            lora_request=lora_request
        )
        
        # 결과 추출
        generated_text = outputs[0].outputs[0].text.strip()
        logger.info(f"✅ 텍스트 생성 완료 (길이: {len(generated_text)})")
        
        return generated_text
        
    except Exception as e:
        logger.error(f"❌ 텍스트 생성 실패: {e}")
        raise


async def stream_handler(job):
    """RunPod stream handler - 실시간 스트리밍 (동기 엔진으로 처리)"""
    try:
        logger.info("📥 Stream 요청 수신")
        
        # 동기 엔진이 없는 경우에만 초기화
        if llm_engine is None:
            logger.info("🔧 동기 엔진 초기화 필요 - 첫 스트림 요청")
            initialize_engine()
        else:
            logger.info("✅ 기존 동기 엔진 재사용")
        
        # 페이로드 검증
        payload = job["input"]
        validated = validate_payload(payload)
        
        # LoRA 어댑터 로드
        adapter_info = load_lora_adapter(validated["hf_repo"], validated["hf_token"])
        lora_request = LoRARequest(
            lora_name=adapter_info["name"],
            lora_int_id=adapter_info["lora_int_id"],
            lora_path=adapter_info["path"]
        )
        
        # 프롬프트 생성
        prompt = create_chat_prompt(
            user_message=validated["prompt"],
            system_message=validated["system_message"]
        )
        
        # 샘플링 파라미터
        sampling_params = SamplingParams(
            temperature=validated["temperature"],
            max_tokens=validated["max_tokens"],
            top_p=validated["top_p"],
            top_k=validated["top_k"],
            repetition_penalty=validated["repetition_penalty"],
        )
        
        logger.info(f"🌊 스트리밍 생성 시작 - LoRA: {validated['hf_repo']}")
        
        # 동기 엔진을 사용한 스트리밍 - 별도 스레드에서 실행 후 청크로 분할
        loop = asyncio.get_event_loop()
        
        def _generate():
            return llm_engine.generate(
                prompts=[prompt],
                sampling_params=sampling_params,
                lora_request=lora_request,
                use_tqdm=False
            )
        
        # 비동기로 실행
        outputs = await loop.run_in_executor(None, _generate)
        generated_text = outputs[0].outputs[0].text
        
        # 청크 단위로 스트리밍
        chunk_size = 8  # 단어 단위
        words = generated_text.split()
        
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size])
            if i + chunk_size < len(words):
                chunk += ' '
            
            yield {
                "chunk": chunk,
                "is_final": i + chunk_size >= len(words),
                "generated_text": ' '.join(words[:i + chunk_size])
            }
            
            # 스트리밍 딜레이
            await asyncio.sleep(0.05)
        
        logger.info("✅ 스트리밍 생성 완료")
        
    except Exception as e:
        logger.error(f"❌ 스트리밍 생성 실패: {e}")
        yield {
            "error": str(e),
            "is_final": True,
            "status": "failed"
        }


def handler(job):
    """RunPod handler - run 엔드포인트 (동기 처리)"""
    try:
        logger.info("📥 Run 요청 수신")
        
        # 엔진 초기화 확인 (싱글톤 보장)
        if llm_engine is None:
            logger.info("🔧 엔진 초기화 필요 - 첫 요청")
            initialize_engine()
        else:
            logger.info("✅ 기존 엔진 재사용")
        
        # 페이로드
        payload = job["input"]
        
        # 텍스트 생성 (동기적으로 처리)
        generated_text = generate_response(payload)
        
        logger.info(f"✅ Run 요청 처리 완료 - 길이: {len(generated_text)}")
        
        return {
            "status": "completed",
            "generated_text": generated_text,
            "output": {
                "generated_text": generated_text
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Run 핸들러 오류: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        }


def sync_handler(job):
    """RunPod sync handler - runsync 엔드포인트 (동기 처리)"""
    try:
        logger.info("📥 RunSync 요청 수신")
        
        # 엔진 초기화 확인 (싱글톤 보장)
        if llm_engine is None:
            logger.info("🔧 엔진 초기화 확인 - 첫 요청")
            initialize_engine()
        else:
            logger.info("✅ 기존 엔진 재사용")
        
        # 페이로드
        payload = job["input"]
        
        # 텍스트 생성
        generated_text = generate_response(payload)
        
        return {
            "status": "completed",
            "generated_text": generated_text,
            "output": {
                "generated_text": generated_text
            }
        }
        
    except Exception as e:
        logger.error(f"❌ RunSync 핸들러 오류: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        }


def get_gpu_memory_info():
    """실시간 GPU 메모리 사용량 모니터링"""
    if not GPU_MONITORING_AVAILABLE:
        return "GPU 모니터링 비활성화"
    
    try:
        if torch.cuda.is_available():
            total_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB
            reserved_memory = torch.cuda.memory_reserved(0) / (1024**3)  # GB
            allocated_memory = torch.cuda.memory_allocated(0) / (1024**3)  # GB
            free_memory = total_memory - reserved_memory
            
            return {
                "total_gb": round(total_memory, 2),
                "reserved_gb": round(reserved_memory, 2),
                "allocated_gb": round(allocated_memory, 2),
                "free_gb": round(free_memory, 2),
                "utilization_percent": round((reserved_memory / total_memory) * 100, 1)
            }
        else:
            return "CUDA 비활성화"
    except Exception as e:
        return f"GPU 메모리 모니터링 오류: {e}"


def log_gpu_memory():
    """간단한 GPU 메모리 로그 출력"""
    memory_info = get_gpu_memory_info()
    if isinstance(memory_info, dict):
        logger.info(f"📊 GPU 메모리: {memory_info['reserved_gb']:.1f}GB/{memory_info['total_gb']:.1f}GB "
                   f"({memory_info['utilization_percent']:.1f}% 사용, {memory_info['free_gb']:.1f}GB 여유)")
    else:
        logger.info(f"📊 GPU 메모리: {memory_info}")


def cleanup_engines():
    """엔진 정리 및 메모리 해제"""
    global llm_engine, _engine_initialized
    
    try:
        logger.info("🧹 엔진 정리 시작...")
        log_gpu_memory()  # 정리 전 메모리 상태
        
        if llm_engine is not None:
            logger.info("🧹 동기 엔진 정리 중...")
            # vLLM 엔진은 자동으로 GPU 메모리를 해제함
            llm_engine = None
            _engine_initialized = False
        
        # GPU 메모리 강제 정리 (선택적)
        if GPU_MONITORING_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("🧹 GPU 캐시 정리 완료")
            
        log_gpu_memory()  # 정리 후 메모리 상태
        logger.info("✅ 엔진 정리 완료")
        
    except Exception as e:
        logger.error(f"❌ 엔진 정리 실패: {e}")


def warmup_test():
    """워커 웜업 테스트"""
    try:
        logger.info("🔥 워커 웜업 시작...")
        
        # 현재 초기화된 엔진이 없으면 웜업 불가
        if llm_engine is None:
            logger.warning("⚠️ 웜업 대상 엔진이 없습니다")
            return False
        
        # 베이스 모델로 간단한 생성 테스트
        start_time = time.time()
        
        # 프롬프트 생성
        prompt = create_chat_prompt(
            user_message="안녕하세요",
            system_message=DEFAULT_SYSTEM_MESSAGE
        )
        
        # 샘플링 파라미터
        sampling_params = SamplingParams(
            temperature=0.7,
            max_tokens=50,
        )
        
        # 텍스트 생성 (베이스 모델)
        outputs = llm_engine.generate(
            prompts=[prompt],
            sampling_params=sampling_params,
        )
        
        generated_text = outputs[0].outputs[0].text.strip()
        generation_time = time.time() - start_time
        
        logger.info(f"✅ 웜업 성공!")
        logger.info(f"📝 생성된 텍스트: '{generated_text[:50]}...'")
        logger.info(f"⏱️ 생성 시간: {generation_time:.2f}초")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 웜업 실패: {e}")
        return False


# RunPod 서버리스 실행
if __name__ == "__main__":
    logger.info("🚀 RunPod vLLM Generation Worker 시작")
    logger.info(f"📋 기본 모델: {DEFAULT_MODEL}")
    
    # 모델 사전 로드
    if PRELOAD_MODEL:
        logger.info("🔧 vLLM 엔진 사전 초기화 중...")
        
        try:
            logger.info("🔧 동기 LLM 엔진으로 초기화 중...")
            initialize_engine(DEFAULT_MODEL)
            logger.info("✅ LLM 엔진 초기화 완료")
            
            # 웜업 테스트
            if llm_engine is not None:
                if warmup_test():
                    logger.info("🔥 워커 웜업 완료 - 최적의 성능으로 요청 대기 중")
                else:
                    logger.warning("⚠️ 웜업 실패 - 첫 요청 시 지연 가능")
                
        except Exception as e:
            logger.error(f"❌ 초기화 실패: {e}")
            logger.info("⚠️ 첫 요청 시 초기화됩니다")
    else:
        logger.info("💤 모델 사전 로드 비활성화 - 첫 요청 시 초기화")
    
    # RunPod 핸들러 등록
    runpod.serverless.start({
        "handler": handler,              # /run 엔드포인트
        "sync_handler": sync_handler,    # /runsync 엔드포인트
        "stream_handler": stream_handler # /stream 엔드포인트 (실시간 스트리밍)
    })