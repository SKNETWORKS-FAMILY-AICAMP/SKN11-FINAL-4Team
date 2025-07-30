# RunPod Fine-tuning Worker Dockerfile
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV TOKENIZERS_PARALLELISM=false
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# 작업 디렉토리 설정
WORKDIR /workspace

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
RUN pip install --no-cache-dir \
    transformers==4.36.2 \
    datasets \
    peft \
    accelerate \
    huggingface-hub \
    runpod \
    aiohttp

# RunPod 핸들러 복사  
COPY finetuning_worker.py /workspace/finetuning_worker.py

# 환경 변수로 모델 캐시 디렉토리 설정
ENV HF_HOME=/workspace/huggingface
ENV TRANSFORMERS_CACHE=/workspace/huggingface/transformers
ENV PYTHONPATH=/workspace

# RunPod 핸들러 설정
CMD ["python", "-u", "/workspace/finetuning_worker.py"]