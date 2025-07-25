#!/bin/bash

# 모든 서비스를 GPU 격리와 함께 시작하는 통합 스크립트

echo "🚀 Starting all services with GPU isolation..."

# 환경 변수 로드
source .env 2>/dev/null || true

# GPU 정보 출력
echo "📊 GPU Configuration:"
echo "  - vLLM Server: GPU $VLLM_GPU_ID (Memory: ${VLLM_GPU_MEMORY_UTILIZATION:-0.5})"
echo "  - Zonos TTS: GPU $TTS_GPU_ID (Memory: ${TTS_GPU_MEMORY_UTILIZATION:-0.3})"
echo "  - Finetuning: GPU $FINETUNING_GPU_ID (Memory: ${FINETUNING_GPU_MEMORY_UTILIZATION:-0.8})"

# 1. Backend 서버 시작 (GPU 사용 안함)
echo "🔧 Starting Backend Server..."
cd backend
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "  ✅ Backend started (PID: $BACKEND_PID)"
cd ..

# 2. vLLM 서버 시작 (GPU 0)
echo "🤖 Starting vLLM Server with GPU $VLLM_GPU_ID..."
CUDA_VISIBLE_DEVICES=$VLLM_GPU_ID nohup uvicorn vllm.app.main:app --host 0.0.0.0 --port 8001 --reload > logs/vllm.log 2>&1 &
VLLM_PID=$!
echo "  ✅ vLLM started (PID: $VLLM_PID)"

# PID 저장
echo "BACKEND_PID=$BACKEND_PID" > .pids
echo "VLLM_PID=$VLLM_PID" >> .pids

echo ""
echo "✅ All services started successfully!"
echo ""
echo "📍 Service URLs:"
echo "  - Backend API: http://localhost:8000"
echo "  - vLLM API: http://localhost:8001"
echo "  - API Docs: http://localhost:8000/docs"
echo ""
echo "📝 Logs:"
echo "  - Backend: logs/backend.log"
echo "  - vLLM: logs/vllm.log"
echo ""
echo "🛑 To stop all services: ./stop_all_services.sh"
echo ""

# Finetuning 사용 예시
echo "🔧 To run finetuning with GPU isolation:"
echo "  CUDA_VISIBLE_DEVICES=$FINETUNING_GPU_ID python -m vllm.pipeline.fine_custom --dataset path/to/dataset.json"