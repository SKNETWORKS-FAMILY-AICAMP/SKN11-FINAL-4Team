# VLLM 서버 - AI 인플루언서 GPU 추론 & 파인튜닝

이 VLLM 서버는 기존 FastAPI 백엔드의 GPU 추론과 파인튜닝 로직을 고성능으로 처리하는 전용 서버입니다.

## 🚀 주요 기능

### GPU 추론
- **비동기 GPU 추론**: VLLM의 AsyncLLMEngine을 사용한 고성능 추론
- **LoRA 어댑터 지원**: 최대 8개의 LoRA 어댑터 동시 로드
- **WebSocket 채팅**: 실시간 채팅 인터페이스
- **메모리 최적화**: 80% GPU 메모리 활용률로 최적화

### 파인튜닝
- **QLoRA 파인튜닝**: 4비트 양자화를 통한 메모리 효율적 파인튜닝
- **Hugging Face 통합**: 자동 모델 업로드 및 배포
- **백그라운드 처리**: 비동기 파인튜닝 작업 처리
- **상태 모니터링**: 실시간 파인튜닝 진행 상황 추적

## 📋 요구사항

- **GPU**: CUDA 지원 GPU (8GB VRAM 이상 권장)
- **Python**: 3.9 이상
- **CUDA**: 11.8 이상
- **메모리**: 시스템 RAM 16GB 이상 권장

## 🛠️ 설치 및 실행

### 1. 의존성 설치

```bash
cd vllm
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 다음 변수들을 설정:

```env
# VLLM 서버 설정
VLLM_HOST=0.0.0.0
VLLM_PORT=8000

# GPU 설정
CUDA_VISIBLE_DEVICES=0
VLLM_USE_V1=0

# 모델 설정
BASE_MODEL=LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct
MAX_MODEL_LEN=2048
GPU_MEMORY_UTILIZATION=0.8

# LoRA 설정
ENABLE_LORA=true
MAX_LORAS=8
MAX_LORA_RANK=64
```

### 3. 서버 실행

```bash
cd vllm
python main.py
```

또는 uvicorn으로 직접 실행:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 🌐 API 엔드포인트

### 기본 정보
- `GET /` - 서버 상태 확인
- `GET /stats` - 서버 통계 정보

### LoRA 어댑터 관리
- `POST /load_adapter` - LoRA 어댑터 로드
- `GET /adapters` - 로드된 어댑터 목록
- `DELETE /adapter/{model_id}` - 어댑터 언로드

### GPU 추론
- `POST /generate` - 텍스트 생성
- `WS /ws/chat/{lora_repo}` - WebSocket 채팅

### 파인튜닝
- `POST /finetuning/start` - 파인튜닝 시작
- `GET /finetuning/status/{task_id}` - 파인튜닝 상태 조회
- `GET /finetuning/tasks` - 파인튜닝 작업 목록

## 🔧 FastAPI 백엔드 통합

### 1. VLLM 클라이언트 서비스

백엔드에 `app/services/vllm_client.py`가 추가되어 VLLM 서버와 통신합니다:

```python
from app.services.vllm_client import get_vllm_client

# 어댑터 로드
vllm_client = await get_vllm_client()
await vllm_client.load_adapter("model_id", "hf_repo_name", "hf_token")

# 응답 생성
result = await vllm_client.generate_response(
    user_message="안녕하세요!",
    influencer_name="AI인플루언서",
    model_id="model_id"
)
```

### 2. 백엔드 설정

`app/core/config.py`에 VLLM 설정 추가:

```python
# VLLM 서버 설정
VLLM_HOST: str = "localhost"
VLLM_PORT: int = 8000
VLLM_TIMEOUT: int = 300
VLLM_ENABLED: bool = True
```

### 3. 폴백 메커니즘

VLLM 서버가 사용 불가능한 경우 자동으로 로컬 모델로 폴백:

1. **WebSocket**: VLLM 서버 → 로컬 transformers 모델
2. **파인튜닝**: VLLM 서버 → 로컬 pipeline/fine_custom.py
3. **어댑터 로드**: VLLM 서버 → 로컬 PEFT 모델 캐싱

## 📊 성능 최적화

### GPU 메모리 관리
- **GPU 메모리 활용률**: 80% (설정 가능)
- **배치 처리**: 최대 256개 시퀀스 동시 처리
- **토큰 배치**: 최대 8192 토큰

### LoRA 어댑터 최적화
- **동시 로드**: 최대 8개 어댑터
- **메모리 공유**: 베이스 모델 공유로 메모리 절약
- **캐싱**: 자주 사용되는 어댑터 메모리 캐싱

### 비동기 처리
- **AsyncLLMEngine**: 비동기 추론 엔진
- **백그라운드 작업**: 파인튜닝 비동기 처리
- **WebSocket**: 실시간 통신

## 🔍 모니터링 및 디버깅

### 로그 확인
```bash
# 실시간 로그 확인
tail -f vllm_server.log

# 에러 로그만 확인
grep ERROR vllm_server.log
```

### GPU 사용률 모니터링
```bash
# GPU 상태 확인
nvidia-smi

# 지속적인 모니터링
watch -n 1 nvidia-smi
```

### API 테스트
```bash
# 서버 상태 확인
curl http://localhost:8000/

# 통계 정보 확인
curl http://localhost:8000/stats

# 어댑터 목록 확인
curl http://localhost:8000/adapters
```

## 🚨 문제 해결

### 일반적인 문제들

1. **CUDA Out of Memory**
   - `GPU_MEMORY_UTILIZATION` 값을 낮춤 (0.7 또는 0.6)
   - `MAX_MODEL_LEN` 값을 줄임
   - 로드된 어댑터 수를 줄임

2. **LoRA 어댑터 로드 실패**
   - Hugging Face 토큰 확인
   - 어댑터 저장소 접근 권한 확인
   - 베이스 모델 호환성 확인

3. **WebSocket 연결 실패**
   - 포트 충돌 확인 (8000번 포트)
   - 방화벽 설정 확인
   - CORS 설정 확인

### 로그 레벨 조정
```python
# main.py에서 로그 레벨 변경
logging.basicConfig(level=logging.DEBUG)  # 더 자세한 로그
logging.basicConfig(level=logging.WARNING)  # 경고만 표시
```

## 🔄 업그레이드 및 유지보수

### 정기 업데이트
```bash
# VLLM 업데이트
pip install --upgrade vllm

# 전체 의존성 업데이트
pip install --upgrade -r requirements.txt
```

### 모델 캐시 정리
```bash
# Hugging Face 캐시 정리
rm -rf ~/.cache/huggingface/

# 임시 파일 정리
rm -rf /tmp/vllm_*
```

## 📞 지원

- **GitHub Issues**: 버그 리포트 및 기능 요청
- **Documentation**: API 문서는 `/docs` 엔드포인트에서 확인
- **Logs**: 상세한 에러 로그는 서버 로그 파일 확인