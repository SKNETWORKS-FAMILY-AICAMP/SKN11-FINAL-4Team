#!/bin/bash

# vLLM 서버 시작 스크립트 - GPU 0 전용

# 환경 변수 로드
source .env 2>/dev/null || true

# GPU 0만 보이도록 설정
export CUDA_VISIBLE_DEVICES=0

echo "🚀 Starting vLLM server with GPU isolation"
echo "📍 CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES (Physical GPU $VLLM_GPU_ID)"
echo "💾 GPU Memory Utilization: $VLLM_GPU_MEMORY_UTILIZATION"

# vLLM 서버 실행
cd vllm
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload