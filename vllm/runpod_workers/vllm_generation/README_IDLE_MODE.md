# vLLM Worker Idle 모드 설정 가이드

## 개요
vLLM Worker가 베이스 모델을 미리 로드하고 idle 상태로 대기하도록 설정하는 방법입니다. 이를 통해 첫 번째 요청의 콜드 스타트 시간을 크게 줄일 수 있습니다.

## 주요 기능

### 1. 모델 사전 로드 (Preloading)
- 워커 시작 시 자동으로 베이스 모델을 GPU 메모리에 로드
- 웜업 테스트를 통해 모델이 즉시 응답 가능한 상태로 준비

### 2. Keep-Alive 메커니즘
- 주기적으로 GPU 메모리 상태를 확인
- 설정된 간격으로 간단한 추론을 실행하여 모델을 활성 상태로 유지
- GPU 메모리에서 모델이 언로드되는 것을 방지

### 3. 환경 변수 설정

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `PRELOAD_MODEL` | `true` | 시작 시 모델 사전 로드 여부 |
| `ENABLE_KEEP_ALIVE` | `true` | Keep-Alive 메커니즘 활성화 여부 |
| `KEEP_ALIVE_INTERVAL` | `300` | Keep-Alive 체크 간격 (초) |
| `KEEP_ALIVE_INFERENCE_INTERVAL` | `3600` | Keep-Alive 추론 실행 간격 (초) |

## 사용 방법

### Docker Compose 사용

```bash
# 기본 설정으로 실행 (모델 사전 로드 + Keep-Alive 활성화)
docker-compose up vllm-worker

# Production 모드로 실행
docker-compose --profile production up vllm-worker-prod
```

### Docker 직접 실행

```bash
# 모든 기능 활성화
docker run --gpus all -p 8000:8000 \
  -e PRELOAD_MODEL=true \
  -e ENABLE_KEEP_ALIVE=true \
  -e KEEP_ALIVE_INTERVAL=300 \
  -e KEEP_ALIVE_INFERENCE_INTERVAL=3600 \
  vllm-worker

# Keep-Alive만 비활성화
docker run --gpus all -p 8000:8000 \
  -e PRELOAD_MODEL=true \
  -e ENABLE_KEEP_ALIVE=false \
  vllm-worker

# 완전한 Lazy Loading (첫 요청 시 초기화)
docker run --gpus all -p 8000:8000 \
  -e PRELOAD_MODEL=false \
  -e ENABLE_KEEP_ALIVE=false \
  vllm-worker
```

### RunPod 환경 변수 설정

RunPod 템플릿이나 워커 설정에서 다음 환경 변수를 추가:

```json
{
  "env": {
    "PRELOAD_MODEL": "true",
    "ENABLE_KEEP_ALIVE": "true",
    "KEEP_ALIVE_INTERVAL": "300",
    "KEEP_ALIVE_INFERENCE_INTERVAL": "3600"
  }
}
```

## 동작 상태 확인

### 로그 확인
```bash
# Docker 로그 확인
docker logs <container-id>

# 주요 로그 메시지
# 🔧 vLLM 엔진 사전 초기화 중...
# ✅ 엔진 초기화 완료
# 🔥 워커 웜업 완료 - 최적의 성능으로 요청 대기 중
# 💓 Keep-Alive 스레드 시작 - 모델이 항상 메모리에 유지됩니다
# 💓 Keep-Alive - GPU 메모리: 2.4/24.0GB 사용 중
# 🔄 Keep-Alive 추론 실행 중...
# ✅ Keep-Alive 추론 완료 - 모델 활성 상태 확인
```

### GPU 메모리 모니터링
```bash
# GPU 메모리 사용량 실시간 확인
watch -n 1 nvidia-smi

# 모델이 로드되면 약 2-3GB의 GPU 메모리가 사용됨
```

## 성능 비교

### 콜드 스타트 (PRELOAD_MODEL=false)
- 첫 요청 시 모델 로드: 10-30초
- 두 번째 요청부터: <1초

### 웜 스타트 (PRELOAD_MODEL=true)
- 첫 요청부터: <1초
- 일관된 빠른 응답 시간

### Keep-Alive 효과
- 활성화 시: 모델이 항상 메모리에 유지
- 비활성화 시: 유휴 시간 후 GPU 메모리에서 언로드될 수 있음

## 리소스 고려사항

### GPU 메모리
- EXAONE-3.5-2.4B 모델: 약 2-3GB GPU 메모리 사용
- Keep-Alive 추론: 추가 메모리 사용 거의 없음

### CPU 사용률
- Keep-Alive 체크: CPU 사용률 <1%
- Keep-Alive 추론: 순간적으로 CPU/GPU 사용

### 비용 최적화
- RunPod Serverless: 요청이 없어도 최소한의 리소스 사용
- 자주 사용되는 워커에 적합
- 거의 사용되지 않는 워커는 PRELOAD_MODEL=false 권장

## 문제 해결

### 모델이 로드되지 않음
```bash
# 환경 변수 확인
docker exec <container-id> env | grep -E "(PRELOAD|KEEP_ALIVE)"

# GPU 메모리 부족 확인
nvidia-smi
```

### Keep-Alive가 작동하지 않음
```bash
# 로그에서 Keep-Alive 메시지 확인
docker logs <container-id> | grep "Keep-Alive"

# 스레드 상태 확인
docker exec <container-id> ps aux | grep python
```

### 메모리 누수
- KEEP_ALIVE_INFERENCE_INTERVAL을 더 길게 설정 (예: 7200)
- 정기적으로 워커 재시작 스케줄링

## 권장 설정

### 높은 트래픽 워커
```env
PRELOAD_MODEL=true
ENABLE_KEEP_ALIVE=true
KEEP_ALIVE_INTERVAL=300
KEEP_ALIVE_INFERENCE_INTERVAL=1800  # 30분
```

### 중간 트래픽 워커
```env
PRELOAD_MODEL=true
ENABLE_KEEP_ALIVE=true
KEEP_ALIVE_INTERVAL=600
KEEP_ALIVE_INFERENCE_INTERVAL=3600  # 1시간
```

### 낮은 트래픽 워커
```env
PRELOAD_MODEL=false
ENABLE_KEEP_ALIVE=false
```

## 모니터링 스크립트

```python
# monitor_worker.py
import requests
import time

def check_worker_status():
    """워커 상태 확인"""
    try:
        # 헬스체크
        response = requests.get("http://localhost:8000/health")
        print(f"✅ 워커 상태: {response.json()}")
        
        # 테스트 요청
        start_time = time.time()
        response = requests.post("http://localhost:8000/generate", 
            json={"prompt": "Hello", "max_tokens": 5})
        latency = time.time() - start_time
        
        print(f"⏱️ 응답 시간: {latency:.2f}초")
        print(f"📝 응답: {response.json().get('generated_text')}")
        
    except Exception as e:
        print(f"❌ 오류: {e}")

# 5분마다 체크
while True:
    check_worker_status()
    time.sleep(300)
```