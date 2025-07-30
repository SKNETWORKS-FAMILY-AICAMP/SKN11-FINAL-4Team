"""
RunPod Serverless Worker for vLLM Generation with LoRA
EXAONE 모델을 사용한 텍스트 생성 (LoRA 어댑터 지원)
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
device = None

# 기본 설정
DEFAULT_MODEL = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
DEFAULT_SYSTEM_MESSAGE = "당신은 도움이 되는 AI 어시스턴트입니다."

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
        
        # vLLM 엔진 초기화
        llm_engine = LLM(
            model=model_name,
            tensor_parallel_size=1,
            trust_remote_code=True,
            dtype="bfloat16" if torch.cuda.is_available() else "float32",
            enable_lora=True,
            max_lora_rank=64,
            max_loras=5,  
            gpu_memory_utilization=gpu_memory_utilization
        )
        
        logger.info("✅ vLLM 엔진 초기화 완료")
        
    except Exception as e:
        logger.error(f"❌ 엔진 초기화 실패: {str(e)}")
        raise

def create_chat_prompt(
    user_message: str,
    system_message: str = DEFAULT_SYSTEM_MESSAGE,
    influencer_name: Optional[str] = None,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """채팅 프롬프트 생성"""
    messages = []
    
    # 시스템 메시지
    if influencer_name:
        system_message = f"당신은 {influencer_name}입니다. {system_message}"
    messages.append({"role": "system", "content": system_message})
    
    # 채팅 히스토리 추가
    if chat_history:
        for msg in chat_history:
            messages.append(msg)
    
    # 사용자 메시지
    messages.append({"role": "user", "content": user_message})
    
    # 토크나이저의 chat template 적용
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    return prompt

def load_lora_adapter(adapter_path: str, adapter_name: str) -> Dict[str, Any]:
    """LoRA 어댑터 로드"""
    global loaded_adapters
    
    if adapter_name in loaded_adapters:
        logger.info(f"어댑터 {adapter_name}이 이미 로드되어 있습니다.")
        return loaded_adapters[adapter_name]
    
    try:
        # Hugging Face Hub에서 다운로드
        if adapter_path.startswith("hf://"):
            repo_id = adapter_path.replace("hf://", "")
            logger.info(f"📥 Hugging Face Hub에서 어댑터 다운로드: {repo_id}")
            local_path = snapshot_download(repo_id)
        else:
            local_path = adapter_path
        
        # LoRA 어댑터 정보 생성
        adapter_info = {
            "name": adapter_name,
            "path": local_path,
            "lora_int_id": len(loaded_adapters) + 1,  # 고유 ID 할당
            "loaded_at": os.path.getmtime(local_path)
        }
        
        loaded_adapters[adapter_name] = adapter_info
        logger.info(f"✅ LoRA 어댑터 로드 완료: {adapter_name}")
        
        return adapter_info
        
    except Exception as e:
        logger.error(f"❌ LoRA 어댑터 로드 실패: {str(e)}")
        raise

def validate_input(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """입력 데이터 검증"""
    # 필수 필드 확인
    if "prompt" not in job_input and "messages" not in job_input:
        raise ValueError("prompt 또는 messages 필드가 필요합니다.")
    
    validated = {
        # 프롬프트 관련
        "prompt": job_input.get("prompt"),
        "messages": job_input.get("messages"),
        "system_message": job_input.get("system_message", DEFAULT_SYSTEM_MESSAGE),
        "influencer_name": job_input.get("influencer_name"),
        
        # 생성 파라미터
        "temperature": float(job_input.get("temperature", 0.7)),
        "max_tokens": int(job_input.get("max_tokens", 512)),
        "top_p": float(job_input.get("top_p", 0.9)),
        "top_k": int(job_input.get("top_k", 50)),
        "repetition_penalty": float(job_input.get("repetition_penalty", 1.1)),
        "stop_sequences": job_input.get("stop_sequences", ["[|Human|", "[|System|", "<|im_end|>", "</s>", "<|eot_id|>"]),
        
        # LoRA 관련
        "lora_adapter": job_input.get("lora_adapter"),
        
        # 스트리밍
        "stream": job_input.get("stream", False),
        
        # 배치 처리
        "n": int(job_input.get("n", 1)),  # 생성할 응답 수
    }
    
    # 프롬프트 생성
    if validated["messages"]:
        # messages 형식인 경우
        validated["prompt"] = tokenizer.apply_chat_template(
            validated["messages"],
            tokenize=False,
            add_generation_prompt=True
        )
    elif not validated["prompt"]:
        # prompt가 없는 경우 에러
        raise ValueError("prompt 또는 messages 중 하나는 필수입니다.")
    else:
        # 일반 prompt인 경우 chat template 적용
        validated["prompt"] = create_chat_prompt(
            user_message=validated["prompt"],
            system_message=validated["system_message"],
            influencer_name=validated["influencer_name"]
        )
    
    return validated

def generate_text(
    prompt: str,
    sampling_params: SamplingParams,
    lora_request: Optional[LoRARequest] = None
) -> List[str]:
    """텍스트 생성"""
    request_id = str(uuid.uuid4())
    
    # 생성 실행
    outputs = llm_engine.generate(
        prompts=[prompt],
        sampling_params=sampling_params,
        lora_request=lora_request
    )
    
    # 결과 추출
    results = []
    for output in outputs:
        for completion in output.outputs:
            results.append(completion.text)
    
    return results

def clean_response(response: str, influencer_name: Optional[str] = None) -> str:
    """응답 정리"""
    # 불필요한 마커 제거
    markers_to_remove = [
        "[|Assistant|]", "[|Human|]", "[|System|]",
        "<|im_start|>", "<|im_end|>", "<|eot_id|>",
        "</s>", "<s>", "assistant\n", "user\n", "system\n"
    ]
    
    cleaned = response
    for marker in markers_to_remove:
        cleaned = cleaned.replace(marker, "")
    
    # 인플루언서 이름 제거 (있는 경우)
    if influencer_name:
        cleaned = cleaned.replace(f"{influencer_name}:", "")
        cleaned = cleaned.replace(f"{influencer_name} :", "")
    
    # 앞뒤 공백 제거
    cleaned = cleaned.strip()
    
    return cleaned

def handler(job):
    """RunPod 핸들러 함수"""
    try:
        logger.info("📥 새로운 생성 요청 수신")
        
        # 엔진 초기화 확인
        if llm_engine is None:
            model_name = job["input"].get("model", DEFAULT_MODEL)
            initialize_engine(model_name)
        
        # 입력 검증
        job_input = validate_input(job["input"])
        
        # LoRA 어댑터 처리
        lora_request = None
        if job_input["lora_adapter"]:
            adapter_info = job_input["lora_adapter"]
            
            # 어댑터 로드
            if isinstance(adapter_info, dict):
                adapter_name = adapter_info.get("name", "custom_adapter")
                adapter_path = adapter_info["path"]
            else:
                # 문자열인 경우 (경로만 제공)
                adapter_path = adapter_info
                adapter_name = os.path.basename(adapter_path)
            
            loaded_adapter = load_lora_adapter(adapter_path, adapter_name)
            
            # LoRA Request 생성
            lora_request = LoRARequest(
                lora_name=adapter_name,
                lora_int_id=loaded_adapter["lora_int_id"],
                lora_path=loaded_adapter["path"]
            )
            
            logger.info(f"🔧 LoRA 어댑터 사용: {adapter_name}")
        
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
        results = generate_text(
            prompt=job_input["prompt"],
            sampling_params=sampling_params,
            lora_request=lora_request
        )
        
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
            "num_generated": len(cleaned_results)
        }
        
        if job_input["lora_adapter"]:
            result["lora_adapter"] = adapter_name
        
        logger.info(f"✅ 텍스트 생성 완료 (길이: {len(result['generated_text'])})")
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

def batch_handler(jobs):
    """배치 처리 핸들러"""
    results = []
    
    # 엔진 초기화 확인
    if llm_engine is None:
        # 첫 번째 job의 모델 사용
        model_name = jobs[0]["input"].get("model", DEFAULT_MODEL) if jobs else DEFAULT_MODEL
        initialize_engine(model_name)
    
    # 모든 요청을 한 번에 처리
    all_prompts = []
    all_sampling_params = []
    all_lora_requests = []
    job_indices = []
    
    for i, job in enumerate(jobs):
        try:
            job_input = validate_input(job["input"])
            
            # LoRA 처리
            lora_request = None
            if job_input["lora_adapter"]:
                # LoRA 어댑터 로드 로직...
                pass  # 위의 handler와 동일한 로직
            
            # 샘플링 파라미터
            sampling_params = SamplingParams(
                temperature=job_input["temperature"],
                max_tokens=job_input["max_tokens"],
                top_p=job_input["top_p"],
                top_k=job_input["top_k"],
                repetition_penalty=job_input["repetition_penalty"],
                stop=job_input["stop_sequences"],
                n=1  # 배치에서는 n=1로 고정
            )
            
            all_prompts.append(job_input["prompt"])
            all_sampling_params.append(sampling_params)
            all_lora_requests.append(lora_request)
            job_indices.append(i)
            
        except Exception as e:
            results.append({
                "status": "failed",
                "error": str(e)
            })
    
    if all_prompts:
        try:
            # 배치 생성
            outputs = llm_engine.generate(
                prompts=all_prompts,
                sampling_params=all_sampling_params[0],  # 모든 요청이 동일한 파라미터 사용
                lora_request=all_lora_requests[0] if all_lora_requests[0] else None
            )
            
            # 결과 매핑
            for i, output in enumerate(outputs):
                job_idx = job_indices[i]
                job_input = validate_input(jobs[job_idx]["input"])
                
                generated_text = output.outputs[0].text
                cleaned_text = clean_response(generated_text, job_input.get("influencer_name"))
                
                results.insert(job_idx, {
                    "status": "success",
                    "generated_text": cleaned_text,
                    "model": DEFAULT_MODEL
                })
                
        except Exception as e:
            # 배치 실패 시 모든 job 실패 처리
            error_result = {
                "status": "failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            for idx in job_indices:
                results.insert(idx, error_result)
    
    return results

def cleanup():
    """GPU 메모리 정리"""
    global llm_engine, loaded_adapters
    
    if llm_engine is not None:
        del llm_engine
        llm_engine = None
    
    loaded_adapters.clear()
    
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.info("🧹 GPU 메모리 정리 완료")

# RunPod 서버리스 실행
if __name__ == "__main__":
    logger.info("🚀 RunPod vLLM Generation Worker 시작")
    logger.info(f"📋 기본 모델: {DEFAULT_MODEL}")
    runpod.serverless.start({
        "handler": handler,
        "batch_handler": batch_handler
    })