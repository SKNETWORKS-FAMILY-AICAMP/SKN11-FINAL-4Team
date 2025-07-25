#!/bin/bash

# Finetuning Worker 시작 스크립트 - GPU 2 전용

# 환경 변수 로드
source .env 2>/dev/null || true

# GPU 2만 보이도록 설정 (또는 사용 가능한 GPU)
export CUDA_VISIBLE_DEVICES=${FINETUNING_GPU_ID:-2}

echo "🔧 Starting Finetuning Worker with GPU isolation"
echo "📍 CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES (Physical GPU $FINETUNING_GPU_ID)"
echo "💾 GPU Memory Utilization: $FINETUNING_GPU_MEMORY_UTILIZATION"

# Finetuning 작업 실행 예시
if [ "$1" ]; then
    echo "🚀 Running finetuning with arguments: $@"
    cd vllm
    python -m pipeline.fine_custom "$@"
else
    echo "ℹ️  Usage: ./start_finetuning.sh [arguments]"
    echo "   Example: ./start_finetuning.sh --dataset path/to/dataset.json"
fi