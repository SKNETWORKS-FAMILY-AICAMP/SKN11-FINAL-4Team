# GPU Isolation Configuration

## Overview
vLLM, Zonos TTS, 그리고 Finetuning Worker가 각각 독립적인 GPU를 사용하도록 완벽하게 분리된 설정입니다.

## GPU 할당
- **GPU 0**: vLLM Server (EXAONE 모델 추론)
- **GPU 1**: Zonos TTS (음성 합성)
- **GPU 2**: Finetuning Worker (모델 파인튜닝)

## 환경 설정 (.env)
```bash
# GPU Configuration
VLLM_GPU_ID=0                      # vLLM 전용 GPU
TTS_GPU_ID=1                       # Zonos TTS 전용 GPU
FINETUNING_GPU_ID=2               # Finetuning 전용 GPU

# GPU Memory Utilization
VLLM_GPU_MEMORY_UTILIZATION=0.5    # vLLM GPU 메모리 사용률 (50%)
TTS_GPU_MEMORY_UTILIZATION=0.3     # TTS GPU 메모리 사용률 (30%)
FINETUNING_GPU_MEMORY_UTILIZATION=0.8  # Finetuning GPU 메모리 사용률 (80%)
```

## 구현 내용

### 1. Zonos TTS (vllm/app/routers/zonos_tts_async.py)
- 하드코딩된 GPU 1 설정을 환경 변수 기반으로 변경
- CUDA_VISIBLE_DEVICES 격리 모드 지원
- 격리된 환경에서는 항상 논리적 GPU 0 사용

### 2. Finetuning Worker (vllm/pipeline/fine_custom.py)
- `device_map="auto"` 대신 명시적 GPU 지정
- 환경 변수 FINETUNING_GPU_ID 사용
- CUDA_VISIBLE_DEVICES 격리 모드 지원

### 3. vLLM Core (vllm/app/core.py)
- GPU 격리 감지 및 적응
- GPU 메모리 충돌 방지 로직
- 환경 변수 기반 메모리 사용률 설정

## 실행 방법

### 통합 실행 (권장)
```bash
# 모든 서비스를 GPU 격리와 함께 시작
./start_all_services.sh

# 모든 서비스 중지
./stop_all_services.sh
```

### 개별 실행
```bash
# vLLM 서버 (GPU 0)
CUDA_VISIBLE_DEVICES=0 uvicorn vllm.app.main:app --host 0.0.0.0 --port 8001

# Finetuning (GPU 2)
CUDA_VISIBLE_DEVICES=2 python -m vllm.pipeline.fine_custom --dataset data.json
```

## GPU 격리 원리
CUDA_VISIBLE_DEVICES 환경 변수를 사용하여 각 프로세스가 볼 수 있는 GPU를 제한합니다:
- `CUDA_VISIBLE_DEVICES=0`: 물리적 GPU 0만 보임 (논리적 GPU 0으로 매핑)
- `CUDA_VISIBLE_DEVICES=1`: 물리적 GPU 1만 보임 (논리적 GPU 0으로 매핑)
- `CUDA_VISIBLE_DEVICES=2`: 물리적 GPU 2만 보임 (논리적 GPU 0으로 매핑)

이렇게 하면 각 프로세스는 자신에게 할당된 GPU만 볼 수 있어 충돌이 발생하지 않습니다.

## 모니터링
```bash
# GPU 사용률 실시간 모니터링
nvidia-smi -l 1

# 특정 GPU만 모니터링
nvidia-smi -i 0,1,2 -l 1
```

## 문제 해결

### GPU 메모리 부족
- `.env` 파일에서 해당 서비스의 GPU_MEMORY_UTILIZATION 값을 낮춤
- 예: `VLLM_GPU_MEMORY_UTILIZATION=0.3` (30%로 감소)

### GPU 충돌 발생 시
1. 모든 서비스 중지: `./stop_all_services.sh`
2. GPU 메모리 정리: `nvidia-smi --gpu-reset`
3. 서비스 재시작: `./start_all_services.sh`

### GPU 수가 부족한 경우
2개의 GPU만 있다면 `.env` 파일을 다음과 같이 수정:
```bash
VLLM_GPU_ID=0
TTS_GPU_ID=1
FINETUNING_GPU_ID=1  # TTS와 같은 GPU 공유 (메모리 사용률 조정 필요)
```