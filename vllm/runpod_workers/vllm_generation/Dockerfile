# RunPod vLLM Generation Worker Dockerfile
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV CUDA_VISIBLE_DEVICES=0

# vLLM 특정 환경 변수
ENV VLLM_USE_MODELSCOPE=false
ENV TOKENIZERS_PARALLELISM=false

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    git \
    build-essential \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Python 버전 확인 및 pip 업그레이드
RUN python3 --version && pip install --upgrade pip setuptools wheel

# PyTorch CUDA 11.8 설치 (vLLM과 호환되는 버전)
RUN pip install torch --index-url https://download.pytorch.org/whl/cu118

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 워커 코드 복사
COPY generation_worker.py .

# 기본 모델 사전 다운로드 (선택사항 - 매우 큰 모델)
RUN python3 -c "from huggingface_hub import snapshot_download; \
    snapshot_download('LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct', cache_dir='/app/models')"

# 환경 변수로 모델 캐시 디렉토리 설정
ENV HF_HOME=/app/models
ENV TRANSFORMERS_CACHE=/app/models
ENV VLLM_CACHE_ROOT=/app/models

# LoRA 어댑터 디렉토리 생성 및 환경 변수 설정
RUN mkdir -p /app/lora_adapters
ENV LORA_ADAPTERS_BASE_PATH=/app/lora_adapters

# 헬스체크
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python3 -c "import torch; import vllm; print('Health check passed')" || exit 1

# RunPod 핸들러 설정
CMD ["python3", "-u", "generation_worker.py"]