#!/bin/bash

# 모든 서비스 중지 스크립트

echo "🛑 Stopping all services..."

# PID 파일 읽기
if [ -f .pids ]; then
    source .pids
    
    # Backend 중지
    if [ ! -z "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        echo "  Stopping Backend (PID: $BACKEND_PID)..."
        kill $BACKEND_PID
    fi
    
    # vLLM 중지
    if [ ! -z "$VLLM_PID" ] && kill -0 $VLLM_PID 2>/dev/null; then
        echo "  Stopping vLLM (PID: $VLLM_PID)..."
        kill $VLLM_PID
    fi
    
    rm .pids
else
    # PID 파일이 없으면 프로세스 이름으로 찾아서 중지
    echo "  No PID file found, searching for processes..."
    
    # uvicorn 프로세스 찾아서 중지
    pkill -f "uvicorn.*app.main:app.*8000"
    pkill -f "uvicorn.*vllm.app.main:app.*8001"
fi

# GPU 메모리 정리
if command -v nvidia-smi &> /dev/null; then
    echo "🧹 Clearing GPU memory cache..."
    python -c "import torch; torch.cuda.empty_cache() if torch.cuda.is_available() else None" 2>/dev/null || true
fi

echo "✅ All services stopped!"