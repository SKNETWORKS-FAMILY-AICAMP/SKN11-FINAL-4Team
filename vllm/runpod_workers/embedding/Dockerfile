# RunPod Embedding Worker Dockerfile
FROM runpod/base:0.4.0-cuda11.8.0

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV CUDA_VISIBLE_DEVICES=0
ENV TOKENIZERS_PARALLELISM=false

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python 버전 확인 및 pip 업그레이드
RUN python3 --version && pip3 install --upgrade pip setuptools wheel

# PyTorch CUDA 11.8 설치
RUN pip3 install torch --index-url https://download.pytorch.org/whl/cu118

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 워커 코드 복사
COPY embedding_worker.py .

# 주요 모델 사전 다운로드 (선택사항)
RUN python3 -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-m3', cache_folder='/app/models')"

# 환경 변수로 모델 캐시 디렉토리 설정
ENV HF_HOME=/app/models
ENV TRANSFORMERS_CACHE=/app/models
ENV SENTENCE_TRANSFORMERS_HOME=/app/models

# 헬스체크
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python3 -c "import torch; import sentence_transformers; print('Health check passed')" || exit 1

# RunPod 핸들러 설정
CMD ["python3", "-u", "embedding_worker.py"]