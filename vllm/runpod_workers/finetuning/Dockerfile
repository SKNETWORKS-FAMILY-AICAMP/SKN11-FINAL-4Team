FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel

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
RUN python3 --version && pip install --upgrade pip setuptools wheel

# PyTorch CUDA 11.8 설치
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 설치된 패키지 확인
RUN pip list | grep -E "transformers|torch|accelerate|peft"

# 워커 코드 복사
COPY finetuning_worker.py .

# 모델 로딩 부분 수정
RUN python3 -c "from transformers import AutoModelForCausalLM, AutoTokenizer; \
    AutoTokenizer.from_pretrained('LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct', trust_remote_code=True); \
    AutoModelForCausalLM.from_pretrained('LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct', torch_dtype='auto', trust_remote_code=True)"


# 환경 변수로 모델 캐시 디렉토리 설정
ENV HF_HOME=/app/models
ENV TRANSFORMERS_CACHE=/app/models
ENV TORCH_HOME=/app/models

# 헬스체크
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python3 -c "import torch; print('Health check passed')" || exit 1

# RunPod 핸들러 설정
CMD ["python3", "-u", "finetuning_worker.py"]