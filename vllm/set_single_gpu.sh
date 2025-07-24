#!/bin/bash
# vLLM 서버를 단일 GPU 모드로 시작하는 스크립트

echo "🚀 vLLM 서버를 단일 GPU 모드로 설정합니다..."

# 단일 GPU만 사용하도록 환경 변수 설정
export CUDA_VISIBLE_DEVICES=0
export VLLM_GPU_IDS=0

# vLLM v1 어텐션 백엔드 비활성화 (호환성 향상)
export VLLM_USE_V1=0

# 로깅 설정
export VLLM_LOGGING_LEVEL=INFO

echo "✅ 환경 변수 설정 완료:"
echo "   - CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
echo "   - VLLM_GPU_IDS=$VLLM_GPU_IDS"
echo "   - VLLM_USE_V1=$VLLM_USE_V1"

# vLLM 서버 시작
echo "🔄 vLLM 서버를 시작합니다..."
cd /Users/snowfall/Documents/SKN/SKN11-FINAL-4Team/vllm
uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload