#!/bin/bash

# 단일 GPU 사용을 위한 환경변수 설정
export CUDA_VISIBLE_DEVICES=0
export VLLM_USE_V1=0
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# vLLM 관련 추가 설정
export VLLM_ATTENTION_BACKEND=FLASHINFER
export VLLM_ALLOW_RUNTIME_LoRA_UPDATING=1

echo "🚀 Starting vLLM server with single GPU mode..."
echo "📍 CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
echo "📍 Working directory: $(pwd)"

# Python 경로 확인
which python3

# 서버 시작
cd /workspace/SKN11-FINAL-4Team/vllm
python3 app/main.py