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
    git-lfs \
    build-essential \
    ninja-build \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install

# Python 버전 확인 및 pip 업그레이드
RUN python3 --version && pip install --upgrade pip setuptools wheel

# PyTorch CUDA 11.8 설치 (vLLM과 호환되는 버전)
RUN pip install torch --index-url https://download.pytorch.org/whl/cu118

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 워커 코드 복사
COPY generation_worker.py .

# 기본 모델 사전 다운로드 - git clone으로 더 빠르게
# GIT_LFS_SKIP_SMUDGE=1로 먼저 메타데이터만 받고, 필요한 파일만 선택적으로 다운로드
ENV GIT_LFS_SKIP_SMUDGE=1
RUN mkdir -p /app/models && \
    cd /app/models && \
    git clone --depth 1 https://huggingface.co/LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct && \
    cd EXAONE-3.5-2.4B-Instruct && \
    git lfs pull && \
    echo "✅ 모델 메타데이터 다운로드 완료"

# 모델 파일은 런타임에 필요시 다운로드 (빌드 시간 단축)
# 필요하면 아래 주석을 해제하여 모델 파일도 미리 다운로드
# RUN cd /app/models/EXAONE-3.5-2.4B-Instruct && \
#     git lfs pull --include="*.safetensors,*.bin"

# 환경 변수로 모델 캐시 디렉토리 설정
ENV HF_HOME=/app/models
ENV TRANSFORMERS_CACHE=/app/models
ENV VLLM_CACHE_ROOT=/app/models

# LoRA 어댑터 캐시 디렉토리 생성
RUN mkdir -p /app/lora_cache

# 모델 사전 로드 환경 변수 설정
ENV PRELOAD_MODEL=true

# 헬스체크
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python3 -c "import torch; import vllm; print('Health check passed')" || exit 1

# RunPod 핸들러 설정
CMD ["python3", "-u", "generation_worker.py"]