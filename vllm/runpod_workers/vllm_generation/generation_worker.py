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

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 전역 변수
llm_engine = None
tokenizer = None
loaded_adapters = {}

# 기본 설정
DEFAULT_MODEL = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
DEFAULT_SYSTEM_MESSAGE = "당신은 도움이 되는 AI 어시스턴트입니다."
PRELOAD_MODEL = os.environ.get("PRELOAD_MODEL", "true").lower() == "true"

# 전역 스트리밍 상태 저장소
STREAMING_STATES = {}


def initialize_engine(model_name: str = DEFAULT_MODEL):
    """vLLM 엔진 초기화"""
    global llm_engine, tokenizer
    
    if llm_engine is not None:
        logger.info("✅ 엔진이 이미 초기화되어 있습니다.")
        return
    
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
            gpu_memory_utilization=0.85,
            max_model_len=4096,
        )
        
        logger.info("✅ vLLM 엔진 초기화 완료")
        
    except Exception as e:
        logger.error(f"❌ 엔진 초기화 실패: {str(e)}")
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


async def generate_response_stream(payload: Dict[str, Any]) -> AsyncIterator[str]:
    """텍스트 생성 (스트리밍)"""
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
        
        # 스트리밍 생성
        logger.info(f"🌊 스트리밍 생성 시작 - LoRA: {validated['hf_repo']}")
        
        # vLLM은 기본적으로 동기 API이므로, 별도 스레드에서 실행
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
        
        # 토큰 단위로 yield
        generated_text = outputs[0].outputs[0].text
        tokens = generated_text.split()  # 간단히 공백으로 분리
        
        for token in tokens:
            yield token + " "
            await asyncio.sleep(0.01)  # 스트리밍 효과
        
        logger.info(f"✅ 스트리밍 생성 완료")
        
    except Exception as e:
        logger.error(f"❌ 스트리밍 생성 실패: {e}")
        raise


def handler(job):
    """RunPod handler - run 엔드포인트 (비동기 작업 ID 반환)"""
    try:
        logger.info("📥 Run 요청 수신")
        
        # 엔진 초기화 확인
        if llm_engine is None:
            initialize_engine()
        
        # 작업 ID 생성
        job_id = str(uuid.uuid4())
        
        # 페이로드
        payload = job["input"]
        
        # 비동기 처리를 위한 작업 정보 반환
        logger.info(f"✅ 작업 생성 완료 - ID: {job_id}")
        
        return {
            "id": job_id,
            "status": "IN_PROGRESS",
            "delayTime": 0
        }
        
    except Exception as e:
        logger.error(f"❌ Run 핸들러 오류: {e}")
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


def sync_handler(job):
    """RunPod sync handler - runsync 엔드포인트 (동기 처리)"""
    try:
        logger.info("📥 RunSync 요청 수신")
        
        # 엔진 초기화 확인
        if llm_engine is None:
            initialize_engine()
        
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


def stream_handler(job):
    """RunPod stream handler - stream 엔드포인트 (스트리밍)"""
    try:
        logger.info("📥 Stream 요청 수신")
        
        # 엔진 초기화 확인
        if llm_engine is None:
            initialize_engine()
        
        # 스트림 ID 생성
        stream_id = str(uuid.uuid4())
        
        # 페이로드
        payload = job["input"]
        
        # 스트리밍 상태 초기화
        streaming_state = {
            "id": stream_id,
            "status": "initializing",
            "tokens": [],
            "generated_text": "",
            "error": None
        }
        
        STREAMING_STATES[stream_id] = streaming_state
        
        # 백그라운드에서 스트리밍 실행
        async def _stream():
            try:
                streaming_state["status"] = "generating"
                
                async for token in generate_response_stream(payload):
                    streaming_state["tokens"].append(token)
                    streaming_state["generated_text"] += token
                
                streaming_state["status"] = "completed"
                
            except Exception as e:
                streaming_state["status"] = "failed"
                streaming_state["error"] = str(e)
                logger.error(f"❌ 스트리밍 오류: {e}")
        
        # 비동기 태스크 시작
        asyncio.create_task(_stream())
        
        logger.info(f"✅ 스트리밍 시작 - ID: {stream_id}")
        
        return {
            "stream_id": stream_id,
            "status": "success",
            "message": f"스트리밍이 시작되었습니다. stream_id: {stream_id}"
        }
        
    except Exception as e:
        logger.error(f"❌ Stream 핸들러 오류: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        }


def warmup_test():
    """워커 웜업 테스트"""
    try:
        logger.info("🔥 워커 웜업 시작...")
        
        # 테스트 페이로드
        test_payload = {
            "hf_token": os.environ.get("HF_TOKEN", ""),
            "hf_repo": "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct",  # 베이스 모델로 테스트
            "system_message": DEFAULT_SYSTEM_MESSAGE,
            "prompt": "안녕하세요",
            "temperature": 0.7,
            "max_tokens": 50
        }
        
        # 베이스 모델로 간단한 생성 테스트
        start_time = time.time()
        
        # 프롬프트 생성
        prompt = create_chat_prompt(
            user_message=test_payload["prompt"],
            system_message=test_payload["system_message"]
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
            initialize_engine(DEFAULT_MODEL)
            logger.info("✅ 엔진 초기화 완료")
            
            # 웜업 테스트
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
        "stream_handler": stream_handler # /stream 엔드포인트
    })