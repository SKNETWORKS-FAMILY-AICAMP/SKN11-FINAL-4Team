# RunPod TTS Worker Dockerfile
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV CUDA_VISIBLE_DEVICES=0
ENV HF_HOME=/app/models
ENV TRANSFORMERS_CACHE=/app/models
ENV TORCH_HOME=/app/models
ENV HF_DATASETS_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
ENV HF_HUB_OFFLINE=0
# PHONEMIZER_ESPEAK_LIBRARY와 PATH는 나중에 설정

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치 (캐시 최적화)
RUN apt-get update && apt-get install -y \
    python3-dev \
    git \
    ffmpeg \
    libsndfile1 \
    espeak \
    espeak-ng \
    espeak-ng-data \
    libespeak-ng1 \
    build-essential \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# pip 업그레이드
RUN pip install --upgrade pip setuptools wheel

# PyTorch 먼저 설치 (CUDA 11.8 호환)
RUN pip install --no-cache-dir \
    torch \
    torchvision \
    torchaudio \
    --index-url https://download.pytorch.org/whl/cu118

# requirements.txt 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# zonos 모듈 복사 (존재 여부 확인)
COPY zonos/ /app/zonos/

# 워커 코드 복사
COPY tts_worker.py .

# 모델 캐시 디렉토리 생성
RUN mkdir -p /app/models

RUN python3 -c "import os;\
from huggingface_hub import snapshot_download;\
os.makedirs('/app/models', exist_ok=True);\
print('Zonos 모델 다운로드 중...');\
snapshot_download('Zyphra/Zonos-v0.1-transformer', cache_dir='/app/models');\
print('Zonos 모델 다운로드 성공');\
"

RUN python3 -c "from transformers import DacModel; \
print('DAC 모델 다운로드 중...'); \
DacModel.from_pretrained('descript/dac_44khz', cache_dir='/app/models'); \
print('DAC 모델 다운로드 성공');"

# 권한 설정
RUN chmod +x tts_worker.py

# 헬스체크 개선
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD sh -c "python3 -c '\
import torch; \
import sys; \
try: \
    if torch.cuda.is_available(): \
        print(f\"CUDA available: {torch.cuda.get_device_name(0)}\"); \
    else: \
        print(\"CUDA not available, using CPU\"); \
    import transformers; \
    print(\"Health check passed\"); \
    sys.exit(0); \
except Exception as e: \
    print(f\"Health check failed: {e}\"); \
    sys.exit(1)'"


# 포트 노출 (필요한 경우)
EXPOSE 8000

# RunPod 핸들러 시작
CMD ["python3", "-u", "tts_worker.py"]
