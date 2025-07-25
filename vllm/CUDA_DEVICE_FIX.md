# CUDA Device Mismatch Fix

## Problem
The error "Expected all tensors to be on the same device, but found at least two devices, cuda:0 and cuda:1!" occurs when vLLM tries to use multiple GPUs but LoRA tensors are loaded on different devices.

## Solution Implemented

### 1. Force Single GPU Mode
- Set `CUDA_VISIBLE_DEVICES=0` to only use the first GPU
- Set `tensor_parallel_size=1` in vLLM configuration
- Add explicit `device="cuda:0"` parameter to AsyncEngineArgs

### 2. Code Changes Made

#### `/vllm/app/core.py`
- Added `os.environ['CUDA_VISIBLE_DEVICES'] = '0'` in `initialize_vllm_engine()`
- Added `device="cuda:0"` parameter to AsyncEngineArgs
- Added CUDA_VISIBLE_DEVICES setting in `restart_engine()`

#### `/vllm/app/routers/generation.py`
- Added error handling for device mismatch errors
- Added device information logging when errors occur
- Engine restart on device mismatch errors

### 3. Startup Script
Created `/vllm/set_single_gpu.sh` to ensure proper environment setup:
```bash
#!/bin/bash
export CUDA_VISIBLE_DEVICES=0
export VLLM_GPU_IDS=0
export VLLM_USE_V1=0
```

## How to Use

### Option 1: Use the startup script
```bash
cd /Users/snowfall/Documents/SKN/SKN11-FINAL-4Team/vllm
./set_single_gpu.sh
```

### Option 2: Set environment variables manually
```bash
export CUDA_VISIBLE_DEVICES=0
export VLLM_GPU_IDS=0
cd /Users/snowfall/Documents/SKN/SKN11-FINAL-4Team/vllm
uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
```

## Verification
After starting the server, check the logs for:
- "🖥️ 단일 GPU 모드: CUDA 디바이스 0 사용"
- "✅ vLLM LoRA 엔진 초기화 완료"

## Additional Notes
- The `enforce_eager=True` parameter disables CUDA graphs to prevent device synchronization issues
- If you need to use multiple GPUs, you'll need to ensure all LoRA adapters are properly distributed across devices
- The current implementation forces all operations to GPU 0 for stability