#!/bin/bash

# Zonos TTS 서비스 시작 스크립트 - GPU 1 전용

# 환경 변수 로드
source .env 2>/dev/null || true

# GPU 1만 보이도록 설정
export CUDA_VISIBLE_DEVICES=1

echo "🎵 Starting Zonos TTS service with GPU isolation"
echo "📍 CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES (Physical GPU $TTS_GPU_ID)"
echo "💾 GPU Memory Utilization: $TTS_GPU_MEMORY_UTILIZATION"

# Zonos TTS는 vLLM 서버의 일부로 실행됨
echo "✅ Zonos TTS will be initialized as part of vLLM server"
echo "   Make sure vLLM server is running on port 8001"