# vLLM Worker 로컬 테스트 가이드

## 개요
이 가이드는 RunPod vLLM Worker를 로컬 환경에서 Docker로 실행하고 테스트하는 방법을 설명합니다.

## 전제 조건

### GPU 환경 (권장)
- NVIDIA GPU (최소 VRAM 8GB 이상)
- NVIDIA Docker 런타임 설치
- CUDA 11.8 이상

### GPU 없는 환경
- Mock Worker를 사용하여 API 테스트만 가능
- 실제 AI 생성은 불가능

## 테스트 방법

### 1. GPU가 있는 경우

#### Docker Compose 사용
```bash
# 빌드 및 실행
docker-compose -f docker-compose.test.yml up --build

# 백그라운드 실행
docker-compose -f docker-compose.test.yml up -d
```

#### Docker 직접 실행
```bash
# 이미지 빌드
docker build -t vllm-worker .

# 컨테이너 실행
docker run --gpus all -p 8000:8000 \
  -v $(pwd)/local_test_server.py:/app/local_test_server.py \
  vllm-worker python3 local_test_server.py
```

### 2. GPU가 없는 경우 (Mock 모드)

```bash
# Mock Worker 설정
cp mock_worker.py generation_worker.py

# 로컬 테스트 서버 실행
python local_test_server.py
```

### 3. 테스트 실행

#### 자동 테스트
```bash
# 전체 테스트 스위트 실행
python test_worker.py
```

#### 수동 테스트

**기본 생성 요청:**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "인공지능의 미래에 대해 설명해주세요.",
    "max_tokens": 200,
    "temperature": 0.7
  }'
```

**채팅 형식:**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "당신은 친절한 AI 어시스턴트입니다."},
      {"role": "user", "content": "Python을 배우는 가장 좋은 방법은?"}
    ],
    "max_tokens": 200
  }'
```

**인플루언서 모드:**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "오늘의 코딩 팁을 공유합니다!",
    "influencer_name": "개발자 김코딩",
    "system_message": "당신은 열정적인 개발자 인플루언서입니다.",
    "max_tokens": 200,
    "temperature": 0.8
  }'
```

**LoRA 어댑터 사용:**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "머신러닝 모델 최적화 방법",
    "lora_adapter": "hf://username/adapter-name",
    "hf_token": "your-hf-token",
    "max_tokens": 200
  }'
```

**멀티 요청 (비동기):**
```bash
# 여러 요청을 동시에 전송
for i in {1..3}; do
  curl -X POST http://localhost:8000/generate/async \
    -H "Content-Type: application/json" \
    -d "{
      \"prompt\": \"테스트 요청 $i\",
      \"max_tokens\": 100
    }" &
done
wait
```

## 엔드포인트

- `GET /` - API 정보
- `GET /health` - 헬스체크
- `POST /generate` - 동기 텍스트 생성
- `POST /generate/async` - 비동기 텍스트 생성 (멀티 요청)
- `POST /generate/stream` - 스트리밍 생성 (개발 중)
- `GET /test` - 자동 테스트 실행

## 테스트 시나리오

1. **기본 생성 테스트**
   - 간단한 프롬프트로 텍스트 생성
   - 생성 파라미터 조정 테스트

2. **채팅 형식 테스트**
   - 시스템 메시지와 사용자 메시지 조합
   - 멀티턴 대화 테스트

3. **인플루언서 모드 테스트**
   - 특정 페르소나로 응답 생성
   - 톤과 스타일 확인

4. **LoRA 어댑터 테스트**
   - 커스텀 어댑터 로드 및 사용
   - 어댑터 없을 때 폴백 확인

5. **성능 테스트**
   - 콜드 스타트 vs 웜 스타트 시간 측정
   - 동시 요청 처리 능력 확인

6. **멀티 요청 테스트**
   - 여러 요청 동시 처리
   - 큐잉 및 스케줄링 확인

## 문제 해결

### GPU 메모리 부족
```bash
# Docker 컨테이너 로그 확인
docker logs <container-id>

# GPU 메모리 사용량 확인
nvidia-smi
```

### 모델 다운로드 실패
- 인터넷 연결 확인
- HuggingFace 토큰 설정 확인
- 디스크 공간 확인 (최소 10GB 필요)

### LoRA 어댑터 로드 실패
- 어댑터 경로 확인
- HuggingFace 리포지토리 접근 권한 확인
- 로컬 어댑터 디렉토리 마운트 확인

## 성능 최적화

1. **GPU 메모리 사용률 조정**
   - `gpu_memory_utilization` 파라미터 조정 (기본 0.85)

2. **동시 요청 수 조정**
   - `max_concurrent_requests` 파라미터 조정
   - GPU 메모리에 따라 자동 조정됨

3. **배치 크기 최적화**
   - `max_num_batched_tokens` 조정
   - `max_num_seqs` 조정

## 프로덕션 배포 참고사항

1. RunPod에 배포 시 이 로컬 테스트 서버는 사용하지 않음
2. 실제 RunPod 환경에서는 `generation_worker.py`의 핸들러가 직접 호출됨
3. 로컬 테스트와 프로덕션 환경의 차이점 주의