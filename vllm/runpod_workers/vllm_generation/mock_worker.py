"""
GPU가 없는 환경에서 테스트를 위한 Mock Worker
실제 vLLM 대신 간단한 응답을 생성
"""
import time
import uuid
import random

# Mock 응답 템플릿
MOCK_RESPONSES = {
    "default": [
        "이것은 테스트 응답입니다. 실제 vLLM은 GPU가 필요합니다.",
        "Mock 응답: {prompt}에 대한 답변입니다.",
        "테스트 중입니다. GPU 환경에서는 실제 AI 응답이 생성됩니다."
    ],
    "python": [
        "Python은 배우기 쉽고 강력한 프로그래밍 언어입니다.",
        "Python의 장점은 간결한 문법과 풍부한 라이브러리입니다.",
        "데이터 과학과 AI 분야에서 Python이 널리 사용됩니다."
    ],
    "ai": [
        "인공지능은 인간의 지능을 모방하는 기술입니다.",
        "머신러닝은 데이터로부터 패턴을 학습하는 AI의 한 분야입니다.",
        "딥러닝은 인공 신경망을 사용하는 머신러닝 기법입니다."
    ]
}

class MockLLM:
    """Mock vLLM 엔진"""
    
    def __init__(self, model_name):
        self.model_name = model_name
        print(f"🎭 Mock LLM 초기화: {model_name}")
    
    def generate(self, prompts, sampling_params, lora_request=None):
        """Mock 텍스트 생성"""
        results = []
        
        for prompt in prompts:
            # 프롬프트에서 키워드 추출
            prompt_lower = prompt.lower()
            
            if "python" in prompt_lower:
                response = random.choice(MOCK_RESPONSES["python"])
            elif "ai" in prompt_lower or "인공지능" in prompt_lower:
                response = random.choice(MOCK_RESPONSES["ai"])
            else:
                response = random.choice(MOCK_RESPONSES["default"]).format(prompt=prompt[:50])
            
            # 토큰 수 제한
            if sampling_params.max_tokens:
                words = response.split()
                response = " ".join(words[:sampling_params.max_tokens])
            
            # Mock 출력 객체
            class MockOutput:
                def __init__(self, text):
                    self.outputs = [type('obj', (object,), {'text': text})]
            
            results.append(MockOutput(response))
            
            # 생성 시간 시뮬레이션
            time.sleep(0.1)
        
        return results

# 실제 워커의 함수들을 Mock으로 대체
llm_engine = None
tokenizer = None
loaded_adapters = {}

def initialize_engine(model_name):
    """Mock 엔진 초기화"""
    global llm_engine
    if llm_engine is None:
        llm_engine = MockLLM(model_name)
        print("✅ Mock 엔진 초기화 완료")

def create_chat_prompt(user_message, system_message, influencer_name=None, chat_history=None):
    """Mock 채팅 프롬프트 생성"""
    prompt = f"System: {system_message}\n"
    if influencer_name:
        prompt += f"Character: {influencer_name}\n"
    prompt += f"User: {user_message}\n"
    return prompt

def load_lora_adapter(adapter_path, adapter_name, hf_token=None):
    """Mock LoRA 어댑터 로드"""
    print(f"🎭 Mock LoRA 어댑터 로드: {adapter_name}")
    return {
        "name": adapter_name,
        "path": adapter_path,
        "lora_int_id": len(loaded_adapters) + 1,
        "loaded_at": time.time()
    }

def validate_input(job_input):
    """입력 검증 (Mock 버전)"""
    return {
        "prompt": job_input.get("prompt", "Hello"),
        "messages": job_input.get("messages"),
        "system_message": job_input.get("system_message", "You are a helpful assistant."),
        "influencer_name": job_input.get("influencer_name"),
        "temperature": float(job_input.get("temperature", 0.7)),
        "max_tokens": int(job_input.get("max_tokens", 100)),
        "top_p": float(job_input.get("top_p", 0.9)),
        "top_k": int(job_input.get("top_k", 50)),
        "repetition_penalty": float(job_input.get("repetition_penalty", 1.1)),
        "stop_sequences": job_input.get("stop_sequences", []),
        "lora_adapter": job_input.get("lora_adapter"),
        "hf_token": job_input.get("hf_token"),
        "stream": job_input.get("stream", False),
        "n": int(job_input.get("n", 1))
    }

def generate_text(prompt, sampling_params, lora_request=None):
    """Mock 텍스트 생성"""
    outputs = llm_engine.generate([prompt], sampling_params, lora_request)
    results = []
    for output in outputs:
        for completion in output.outputs:
            results.append(completion.text)
    return results

def clean_response(response, influencer_name=None):
    """응답 정리 (Mock 버전)"""
    return response.strip()

# Mock 핸들러
def handler(job):
    """Mock 핸들러"""
    return sync_handler(job)

def sync_handler(job):
    """Mock 동기 핸들러"""
    try:
        print("🎭 Mock 생성 요청 처리 중...")
        
        # 엔진 초기화
        if llm_engine is None:
            initialize_engine("mock-model")
        
        # 입력 검증
        job_input = validate_input(job["input"])
        
        # Mock 샘플링 파라미터
        class MockSamplingParams:
            def __init__(self, **kwargs):
                self.temperature = kwargs.get("temperature", 0.7)
                self.max_tokens = kwargs.get("max_tokens", 100)
                self.top_p = kwargs.get("top_p", 0.9)
                self.top_k = kwargs.get("top_k", 50)
                self.repetition_penalty = kwargs.get("repetition_penalty", 1.1)
                self.stop = kwargs.get("stop", [])
                self.n = kwargs.get("n", 1)
        
        sampling_params = MockSamplingParams(
            temperature=job_input["temperature"],
            max_tokens=job_input["max_tokens"],
            top_p=job_input["top_p"],
            top_k=job_input["top_k"],
            repetition_penalty=job_input["repetition_penalty"],
            stop=job_input["stop_sequences"],
            n=job_input["n"]
        )
        
        # 프롬프트 준비
        if job_input["messages"]:
            # 채팅 형식
            prompt = "Chat: " + str(job_input["messages"])
        else:
            prompt = job_input["prompt"]
        
        # Mock 생성
        results = generate_text(prompt, sampling_params)
        
        # 응답 정리
        cleaned_results = [clean_response(r) for r in results]
        
        return {
            "status": "success",
            "generated_text": cleaned_results[0] if len(cleaned_results) == 1 else cleaned_results,
            "model": "mock-model",
            "used_lora": False,
            "temperature": job_input["temperature"],
            "max_tokens": job_input["max_tokens"],
            "num_generated": len(cleaned_results),
            "mock_mode": True
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": f"Mock 생성 오류: {str(e)}",
            "mock_mode": True
        }

def stream_handler(job):
    """Mock 스트리밍 핸들러"""
    stream_id = str(uuid.uuid4())
    return {
        "status": "success",
        "stream_id": stream_id,
        "message": "Mock 스트리밍 - GPU가 필요합니다",
        "mock_mode": True
    }

def batch_handler(jobs):
    """Mock 배치 핸들러"""
    return [sync_handler(job) for job in jobs]

# 웜업 테스트
def warmup_test():
    """Mock 웜업 테스트"""
    print("🎭 Mock 웜업 테스트 실행 중...")
    time.sleep(1)
    print("✅ Mock 웜업 완료")
    return True

# 정리 함수
def cleanup():
    """Mock 정리"""
    print("🧹 Mock 정리 완료")

print("="*50)
print("🎭 Mock Worker 모드로 실행 중")
print("⚠️  GPU가 없어서 실제 vLLM 대신 Mock 응답을 생성합니다")
print("💡 실제 환경에서는 GPU와 함께 vLLM이 실행됩니다")
print("="*50)