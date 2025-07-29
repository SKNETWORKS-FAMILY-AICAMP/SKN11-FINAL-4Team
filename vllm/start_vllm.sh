#!/bin/bash

# vLLM 서버 시작 스크립트

# 환경 변수 로드
source .env 2>/dev/null || true

# GPU 설정은 각 프로세스에서 개별적으로 처리
# 메인 프로세스에서는 CUDA_VISIBLE_DEVICES를 설정하지 않음
echo "🚀 Starting vLLM server"
echo "📍 vLLM GPU ID: $VLLM_GPU_ID"
echo "📍 TTS GPU ID: $TTS_GPU_ID"
echo "📍 RAG GPU ID: $RAG_GPU_ID"
echo "📍 Finetuning GPU ID: $FINETUNING_GPU_ID"
echo "💾 GPU Memory Utilization: $VLLM_GPU_MEMORY_UTILIZATION"

# vLLM 서버 실행
cd vllm
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload