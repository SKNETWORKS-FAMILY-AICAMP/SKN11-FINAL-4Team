#!/bin/bash

# 모든 격리된 서비스 중지 스크립트

echo "🛑 Stopping all isolated services..."

# PID 파일 읽기
if [ -f .pids ]; then
    source .pids
    
    # Backend 중지
    if [ ! -z "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        echo "  Stopping Backend (PID: $BACKEND_PID)..."
        kill -TERM $BACKEND_PID
        sleep 1
        kill -9 $BACKEND_PID 2>/dev/null || true
    fi
    
    # Zonos TTS 중지
    if [ ! -z "$TTS_PID" ] && kill -0 $TTS_PID 2>/dev/null; then
        echo "  Stopping Zonos TTS (PID: $TTS_PID)..."
        kill -TERM $TTS_PID
        sleep 1
        kill -9 $TTS_PID 2>/dev/null || true
    fi
    
    # vLLM 중지
    if [ ! -z "$VLLM_PID" ] && kill -0 $VLLM_PID 2>/dev/null; then
        echo "  Stopping vLLM (PID: $VLLM_PID)..."
        kill -TERM $VLLM_PID
        sleep 1
        kill -9 $VLLM_PID 2>/dev/null || true
    fi
    
    rm .pids
else
    echo "  No PID file found, searching for processes..."
    
    # 프로세스 이름으로 찾아서 중지
    pkill -f "uvicorn.*app.main:app.*8000" || true
    pkill -f "uvicorn.*app.main:app.*8001" || true
    pkill -f "python.*zonos_tts_service/main.py" || true
fi

# GPU 메모리 정리
if command -v nvidia-smi &> /dev/null; then
    echo "🧹 Clearing GPU memory cache..."
    
    # 각 GPU별로 메모리 정리
    for gpu_id in 0 1 2; do
        if nvidia-smi -i $gpu_id &> /dev/null; then
            echo "  Clearing GPU $gpu_id memory..."
            CUDA_VISIBLE_DEVICES=$gpu_id python -c "
import torch
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    print(f'    ✅ GPU {torch.cuda.current_device()} memory cleared')
" 2>/dev/null || true
        fi
    done
fi

echo "✅ All services stopped and GPU memory cleared!"