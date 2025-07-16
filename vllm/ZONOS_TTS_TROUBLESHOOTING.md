# Zonos TTS 문제 해결 가이드

## 발생한 오류
PyTorch 컴파일 중 오류가 발생했습니다. 이는 주로 다음과 같은 원인으로 발생합니다:

1. **torch.compile 관련 문제**: PyTorch 2.x의 torch.compile 기능이 특정 환경에서 불안정할 수 있습니다.
2. **CUDA 버전 불일치**: PyTorch와 CUDA 버전이 맞지 않을 때 발생합니다.
3. **메모리 부족**: GPU 메모리가 부족할 때 발생할 수 있습니다.

## 적용된 수정사항

### 1. torch.compile 비활성화
`/app/routers/zonos_tts.py`와 `/app/routers/zonos_tts_async.py`에서:
```python
codes = zonos_model.generate(
    conditioning, 
    cfg_scale=request.cfg_scale,
    disable_torch_compile=True,  # 추가됨
    progress_bar=False           # 추가됨
)
```

### 2. 향상된 에러 처리
더 구체적인 에러 메시지를 제공하도록 수정했습니다:
- cfg_scale 관련 오류 시 명확한 안내
- CUDA 관련 오류 시 구체적인 메시지
- 전체 스택 트레이스 로깅

### 3. 디버깅 스크립트 추가
`test_zonos_debug.py`를 생성하여 모델을 직접 테스트할 수 있습니다.

## 추가 권장사항

### 1. 환경 확인
```bash
# PyTorch와 CUDA 버전 확인
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.version.cuda}')"

# GPU 메모리 확인
nvidia-smi
```

### 2. cfg_scale 값 조정
- **절대 사용하면 안 되는 값**: 1.0
- **권장 범위**: 2.0 ~ 5.0
- **기본값**: 4.0

### 3. 메모리 최적화
큰 텍스트를 처리할 때는:
```python
# max_new_tokens를 줄여서 메모리 사용량 감소
codes = model.generate(
    conditioning,
    cfg_scale=4.0,
    max_new_tokens=86 * 10,  # 10초 분량으로 제한
    disable_torch_compile=True
)
```

### 4. 서버 재시작
변경사항 적용 후 서버를 재시작하세요:
```bash
# 서버 종료 (Ctrl+C)
# 서버 재시작
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 테스트 방법

### 1. 디버깅 스크립트 실행
```bash
cd /workspace/SKN11-FINAL-4Team/vllm
python test_zonos_debug.py
```

### 2. API 테스트
```bash
# 간단한 TTS 생성 테스트
curl -X POST "http://localhost:8000/zonos/generate_tts_simple" \
  -F "text=안녕하세요"

# 상태 확인
curl "http://localhost:8000/zonos/zonos_status"
```

## 여전히 문제가 발생한다면

1. **GPU 드라이버 업데이트**
   ```bash
   nvidia-smi  # 현재 드라이버 버전 확인
   ```

2. **PyTorch 재설치**
   ```bash
   pip install torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu118
   ```

3. **메모리 정리**
   ```python
   import torch
   torch.cuda.empty_cache()
   ```

4. **CPU 모드로 전환** (임시 해결책)
   ```python
   device = torch.device("cpu")
   ```

## 로그 확인
에러 발생 시 상세 로그를 확인하세요:
```bash
# uvicorn 로그에서 상세 정보 확인
tail -f /tmp/zonos_tts_error.log  # 로그 파일 경로는 설정에 따라 다를 수 있음
```