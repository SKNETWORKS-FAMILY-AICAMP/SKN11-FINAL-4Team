# 완벽한 GPU 격리 구현

## 개요
vLLM, Zonos TTS, Finetuning Worker가 각각 **완전히 독립된 프로세스**로 실행되어 GPU 충돌이 발생하지 않습니다.

## 핵심 구현 사항

### 1. 프로세스 격리
- **별도 프로세스**: 각 서비스가 독립적인 Python 프로세스로 실행
- **CUDA 컨텍스트 격리**: 각 프로세스는 자신만의 CUDA 컨텍스트 보유
- **환경 변수 격리**: `CUDA_VISIBLE_DEVICES`로 각 프로세스가 볼 수 있는 GPU 제한

### 2. 서비스 구조
```
├── Backend (포트 8000) - GPU 미사용
├── vLLM Server (포트 8001) - GPU 0 전용
├── Zonos TTS Service (포트 8002) - GPU 1 전용  
└── Finetuning Worker - GPU 2 전용
```

### 3. 구현 파일
- **Zonos TTS 독립 서비스**: `zonos_tts_service/main.py`
- **vLLM 클라이언트**: `vllm/app/routers/zonos_tts_client.py`
- **GPU 컨텍스트 매니저**: `vllm/app/gpu_context_manager.py`
- **격리된 파인튜닝**: `vllm/pipeline/isolated_finetuning.py`

## 실행 방법

### 모든 서비스 시작
```bash
./start_services_isolated.sh
```

### 모든 서비스 중지
```bash
./stop_services_isolated.sh
```

### 개별 서비스 실행
```bash
# Zonos TTS (GPU 1)
CUDA_VISIBLE_DEVICES=1 python zonos_tts_service/main.py

# vLLM (GPU 0)
CUDA_VISIBLE_DEVICES=0 python -m uvicorn vllm.app.main:app --port 8001

# Finetuning (GPU 2)
CUDA_VISIBLE_DEVICES=2 python -m vllm.pipeline.isolated_finetuning --config config.json
```

## GPU 격리 원리

### 1. CUDA_VISIBLE_DEVICES
- 프로세스 시작 전에 환경 변수 설정
- 해당 프로세스는 지정된 GPU만 인식
- 물리적 GPU가 논리적 GPU 0으로 매핑됨

### 2. torch.multiprocessing
- `spawn` 방식 사용으로 완전히 새로운 Python 인터프리터 생성
- 각 프로세스는 독립적인 메모리 공간과 CUDA 컨텍스트 보유

### 3. 프로세스 간 통신
- vLLM → Zonos TTS: HTTP API 통신
- Backend → vLLM: HTTP API 통신
- 공유 메모리나 GPU 컨텍스트 없음

## 모니터링

### GPU 사용률 실시간 확인
```bash
watch -n 1 nvidia-smi
```

### 프로세스별 GPU 메모리 확인
```bash
nvidia-smi pmon -i 0,1,2
```

### 서비스 상태 확인
```bash
# Zonos TTS 상태
curl http://localhost:8002/

# vLLM 상태  
curl http://localhost:8001/health

# GPU 정보
curl http://localhost:8002/gpu-info
```

## 장점

1. **완벽한 격리**: 각 서비스가 독립 프로세스로 GPU 충돌 없음
2. **안정성**: 한 서비스 장애가 다른 서비스에 영향 없음
3. **확장성**: 서비스별 독립적인 스케일링 가능
4. **모니터링**: 프로세스별 리소스 사용량 추적 용이

## 주의사항

1. **GPU 수**: 최소 3개의 GPU 필요 (또는 `.env`에서 조정)
2. **메모리**: 각 프로세스가 독립적으로 메모리 사용
3. **포트**: 각 서비스가 다른 포트 사용 확인

## 문제 해결

### GPU 메모리 부족
```bash
# .env 파일에서 메모리 사용률 조정
VLLM_GPU_MEMORY_UTILIZATION=0.3
TTS_GPU_MEMORY_UTILIZATION=0.2
```

### 프로세스 강제 종료
```bash
# 특정 GPU의 모든 프로세스 종료
sudo fuser -v /dev/nvidia1
sudo fuser -k /dev/nvidia1
```

### GPU 리셋
```bash
sudo nvidia-smi --gpu-reset -i 0,1,2
```