"""
RunPod Serverless Worker for vLLM Generation
"""
import runpod
from vllm import LLM, SamplingParams
import os

# 전역 모델 변수
llm_engine = None

def initialize_model():
    """vLLM 엔진 초기화"""
    global llm_engine
    
    if llm_engine is None:
        model_name = os.environ.get("MODEL_NAME", "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct")
        llm_engine = LLM(
            model=model_name,
            tensor_parallel_size=1,
            trust_remote_code=True,
            enable_lora=True,
            max_lora_rank=64,
            gpu_memory_utilization=0.9
        )
        print(f"✅ vLLM 엔진 초기화 완료: {model_name}")

def handler(job):
    """RunPod 핸들러 함수"""
    try:
        # 모델 초기화 확인
        initialize_model()
        
        # 입력 파라미터 추출
        job_input = job["input"]
        prompt = job_input["prompt"]
        
        # 샘플링 파라미터
        sampling_params = SamplingParams(
            temperature=job_input.get("temperature", 0.7),
            max_tokens=job_input.get("max_tokens", 512),
            top_p=job_input.get("top_p", 0.9),
            repetition_penalty=job_input.get("repetition_penalty", 1.0),
            stop=job_input.get("stop", None)
        )
        
        # LoRA 어댑터 처리
        lora_request = None
        if "lora_adapter" in job_input:
            from vllm.lora.request import LoRARequest
            lora_request = LoRARequest(
                lora_name=job_input["lora_adapter"]["name"],
                lora_int_id=job_input["lora_adapter"]["id"],
                lora_path=job_input["lora_adapter"]["path"]
            )
        
        # 텍스트 생성
        outputs = llm_engine.generate(
            prompts=[prompt],
            sampling_params=sampling_params,
            lora_request=lora_request
        )
        
        generated_text = outputs[0].outputs[0].text
        
        return {
            "generated_text": generated_text,
            "tokens_used": len(outputs[0].outputs[0].token_ids),
            "status": "success"
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "status": "failed"
        }

# RunPod 서버리스 실행
runpod.serverless.start({"handler": handler})