# RunPod Worker 마이그레이션 가이드

## 기존 API에서 RunPod Worker로 전환

### 1. TTS 서비스

**기존 API 호출:**
```python
# 기존 방식
response = requests.post("http://localhost:8000/api/v1/zonos/generate_tts", json={
    "text": "안녕하세요",
    "emotion_name": "happy",
    "upload_to_s3": True
})
```

**RunPod Worker 호출:**
```python
# RunPod 방식
import runpod

result = runpod.run(
    endpoint_id=RUNPOD_TTS_ENDPOINT_ID,
    input={
        "text": "안녕하세요",
        "emotion_name": "happy"
    }
)

# S3 업로드는 백엔드에서 처리
if result["status"] == "success":
    audio_base64 = result["audio_base64"]
    # 백엔드에서 S3 업로드 처리
```

### 2. Embedding 서비스

**기존 API 호출:**
```python
# 기존 방식
response = requests.post("http://localhost:8000/api/v1/embed", json={
    "texts": ["텍스트1", "텍스트2"],
    "model_name": "BAAI/bge-m3"
})
```

**RunPod Worker 호출:**
```python
# RunPod 방식
result = runpod.run(
    endpoint_id=RUNPOD_EMBEDDING_ENDPOINT_ID,
    input={
        "texts": ["텍스트1", "텍스트2"],
        "model_name": "bge-m3",  # 또는 전체 경로
        "return_format": "list"
    }
)
```

### 3. Fine-tuning 서비스

**기존 API 호출:**
```python
# 기존 방식
response = requests.post("http://localhost:8000/api/v1/finetuning/start", json={
    "qa_data": [...],
    "system_message": "...",
    "hf_token": "...",
    "hf_repo_id": "..."
})
```

**RunPod Worker 호출:**
```python
# RunPod 방식 (동일)
result = runpod.run(
    endpoint_id=RUNPOD_FINETUNING_ENDPOINT_ID,
    input={
        "qa_data": [...],
        "system_message": "...",
        "hf_token": "...",
        "hf_repo_id": "..."
    }
)
```

### 4. Generation 서비스

**기존 API 호출:**
```python
# 기존 방식
response = requests.post("http://localhost:8000/api/v1/generate", json={
    "user_message": "안녕하세요",
    "system_message": "친절한 AI",
    "model_id": "custom-lora"
})
```

**RunPod Worker 호출:**
```python
# RunPod 방식
result = runpod.run(
    endpoint_id=RUNPOD_VLLM_ENDPOINT_ID,
    input={
        "prompt": "안녕하세요",
        "system_message": "친절한 AI",
        "lora_adapter": {
            "name": "custom-lora",
            "path": "hf://username/repo-name"
        }
    }
)
```

## 주요 변경사항

### 작업 상태 추적

**기존:**
```python
# 작업 ID로 상태 확인
status = requests.get(f"http://localhost:8000/api/v1/task_status/{task_id}")
```

**RunPod:**
```python
# RunPod API로 상태 확인
status = runpod.status(endpoint_id, job_id)
```

### 배치 처리

**RunPod의 배치 처리 활용:**
```python
# 여러 요청을 한 번에 처리
results = runpod.run_batch(
    endpoint_id=RUNPOD_EMBEDDING_ENDPOINT_ID,
    inputs=[
        {"texts": ["텍스트1"]},
        {"texts": ["텍스트2"]},
        {"texts": ["텍스트3"]}
    ]
)
```

## 백엔드 통합 예시

```python
from app.utils.runpod_client import get_runpod_client, RunPodEndpoint

class AIService:
    def __init__(self):
        self.runpod = get_runpod_client()
    
    async def generate_tts(self, text: str, emotion: str):
        # RunPod 호출
        result = await self.runpod.run_sync(
            endpoint=RunPodEndpoint.TTS,
            input_data={
                "text": text,
                "emotion_name": emotion
            }
        )
        
        # S3 업로드 처리
        if result["status"] == "success":
            audio_data = base64.b64decode(result["audio_base64"])
            s3_url = await self.upload_to_s3(audio_data)
            return {"audio_url": s3_url}
        
        raise Exception(result.get("error"))
```

## 환경 변수 설정

```bash
# .env 파일
RUNPOD_API_KEY=your-api-key
RUNPOD_TTS_ENDPOINT_ID=your-tts-endpoint-id
RUNPOD_EMBEDDING_ENDPOINT_ID=your-embedding-endpoint-id
RUNPOD_FINETUNING_ENDPOINT_ID=your-finetuning-endpoint-id
RUNPOD_VLLM_ENDPOINT_ID=your-vllm-endpoint-id
```

## 모니터링 및 로깅

RunPod 대시보드에서 제공하는 기능:
- 실시간 GPU 사용률
- 요청/응답 로그
- 에러 추적
- 비용 모니터링
- 자동 스케일링 지표

## 비용 최적화 팁

1. **적절한 GPU 선택**
   - TTS/Embedding: RTX 3090 (충분)
   - Fine-tuning/Generation: A100 (필요시)

2. **Idle Timeout 설정**
   - 자주 사용: 300초
   - 가끔 사용: 60초

3. **배치 처리 활용**
   - 개별 요청보다 배치 처리가 효율적

4. **볼륨 캐싱**
   - 모델 파일은 볼륨에 저장하여 재사용