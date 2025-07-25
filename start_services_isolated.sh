#!/bin/bash

# 모든 서비스를 완전히 격리된 프로세스로 실행하는 스크립트

echo "🚀 Starting all services with complete GPU isolation..."

# 환경 변수 로드
source .env 2>/dev/null || true

# 로그 디렉토리 생성
mkdir -p logs

# GPU 정보 출력
echo "📊 GPU Configuration:"
echo "  - vLLM Server: GPU $VLLM_GPU_ID (Memory: ${VLLM_GPU_MEMORY_UTILIZATION:-0.5})"
echo "  - Zonos TTS: GPU $TTS_GPU_ID (Memory: ${TTS_GPU_MEMORY_UTILIZATION:-0.3})"  
echo "  - Finetuning: GPU $FINETUNING_GPU_ID (Memory: ${FINETUNING_GPU_MEMORY_UTILIZATION:-0.8})"
echo ""

# 1. Backend 서버 시작 (GPU 사용 안함)
echo "🔧 Starting Backend Server..."
cd backend
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT:-8000} --reload > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "  ✅ Backend started (PID: $BACKEND_PID, Port: ${BACKEND_PORT:-8000})"
cd ..

# 2초 대기
sleep 2

# 2. Zonos TTS 서비스 시작 (독립 프로세스, GPU 1)
echo "🎵 Starting Zonos TTS Service (Isolated Process)..."
cd zonos_tts_service
CUDA_VISIBLE_DEVICES=$TTS_GPU_ID nohup python main.py > ../logs/zonos_tts.log 2>&1 &
TTS_PID=$!
echo "  ✅ Zonos TTS started (PID: $TTS_PID, Port: ${TTS_SERVICE_PORT:-8002}, GPU: $TTS_GPU_ID)"
cd ..

# 2초 대기
sleep 2

# 3. vLLM 서버 시작 (GPU 0)
echo "🤖 Starting vLLM Server..."
cd vllm
CUDA_VISIBLE_DEVICES=$VLLM_GPU_ID nohup python -m uvicorn app.main:app --host 0.0.0.0 --port ${VLLM_PORT:-8001} --reload > ../logs/vllm.log 2>&1 &
VLLM_PID=$!
echo "  ✅ vLLM started (PID: $VLLM_PID, Port: ${VLLM_PORT:-8001}, GPU: $VLLM_GPU_ID)"
cd ..

# PID 저장
cat > .pids << EOF
BACKEND_PID=$BACKEND_PID
TTS_PID=$TTS_PID  
VLLM_PID=$VLLM_PID
EOF

echo ""
echo "✅ All services started successfully with complete GPU isolation!"
echo ""
echo "📍 Service URLs:"
echo "  - Backend API: http://localhost:${BACKEND_PORT:-8000}"
echo "  - vLLM API: http://localhost:${VLLM_PORT:-8001}"
echo "  - Zonos TTS: http://localhost:${TTS_SERVICE_PORT:-8002}"
echo "  - API Docs: http://localhost:${BACKEND_PORT:-8000}/docs"
echo ""
echo "📝 Logs:"
echo "  - Backend: logs/backend.log"
echo "  - vLLM: logs/vllm.log"
echo "  - Zonos TTS: logs/zonos_tts.log"
echo ""
echo "🛑 To stop all services: ./stop_services_isolated.sh"
echo ""
echo "🔧 To run finetuning with GPU isolation:"
echo "  CUDA_VISIBLE_DEVICES=$FINETUNING_GPU_ID python -m vllm.pipeline.isolated_finetuning --config config.json"
echo ""
echo "📊 Monitor GPU usage:"
echo "  watch -n 1 nvidia-smi"