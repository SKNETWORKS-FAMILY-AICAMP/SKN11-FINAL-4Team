"""
파인튜닝 비동기 처리를 위한 멀티프로세싱 모듈
TTS와 유사한 방식으로 별도 프로세스에서 파인튜닝 실행
"""

import asyncio
import logging
import os
import multiprocessing as mp
from multiprocessing import Queue, Process
import signal
import sys
import time
from typing import Dict, List, Optional, Any
import json
import traceback

logger = logging.getLogger(__name__)

# 멀티프로세싱 관련 전역 변수
finetuning_process = None
finetuning_request_queue = None
finetuning_response_queue = None
finetuning_status_dict = None

def finetuning_worker_process(request_queue: Queue, response_queue: Queue, status_dict: dict):
    """파인튜닝 워커 프로세스"""
    def signal_handler(signum, frame):
        logger.info("🛑 파인튜닝 워커 프로세스 종료 신호 수신")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # GPU 설정
    finetuning_gpu_id = int(os.getenv('FINETUNING_GPU_ID', '0'))
    
    # 부모 프로세스의 CUDA_VISIBLE_DEVICES를 무시하고 새로 설정
    if 'CUDA_VISIBLE_DEVICES' in os.environ:
        logger.info(f"⚠️ 부모 프로세스의 CUDA_VISIBLE_DEVICES={os.environ['CUDA_VISIBLE_DEVICES']} 무시")
    
    os.environ['CUDA_VISIBLE_DEVICES'] = str(finetuning_gpu_id)
    
    # PyTorch 메모리 최적화 설정
    os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:512'
    
    logger.info(f"🔧 파인튜닝 워커 시작")
    logger.info(f"🖥️ CUDA_VISIBLE_DEVICES={os.environ['CUDA_VISIBLE_DEVICES']} (물리적 GPU {finetuning_gpu_id})")
    logger.info(f"📍 파인튜닝은 GPU {finetuning_gpu_id}번에서 실행됩니다")
    logger.info(f"⚙️ PyTorch CUDA 메모리 최적화 설정: {os.environ['PYTORCH_CUDA_ALLOC_CONF']}")
    
    while True:
        try:
            # 요청 대기
            request = request_queue.get()
            
            if request is None:  # 종료 신호
                break
            
            task_id = request['task_id']
            logger.info(f"📥 파인튜닝 요청 수신: {task_id}")
            
            # 상태 업데이트
            status_dict[task_id] = {
                'status': 'processing',
                'progress': 0,
                'message': '파인튜닝 시작'
            }
            
            try:
                # fine_custom 모듈 import
                from pipeline import fine_custom
                
                # GPU 메모리 체크
                import torch
                if torch.cuda.is_available():
                    gpu_mem_before = torch.cuda.memory_allocated() / 1024**3
                    gpu_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                    logger.info(f"🖥️ GPU 메모리 상태: {gpu_mem_before:.2f}GB / {gpu_total:.2f}GB")
                    
                    # 메모리 부족 경고
                    available_mem = gpu_total - gpu_mem_before
                    if available_mem < 10:  # 10GB 미만이면 경고
                        logger.warning(f"⚠️ GPU 메모리 부족 경고: 사용 가능 {available_mem:.2f}GB")
                
                # 파인튜닝 실행
                logger.info(f"🚀 파인튜닝 실행 중: {task_id}")
                hf_model_url = fine_custom.main(
                    qa_data=request['qa_data'],
                    system_message=request['system_message'],
                    hf_token=request['hf_token'],
                    hf_repo_id=request['hf_repo_id'],
                    training_epochs=request['training_epochs']
                )
                
                # 성공 응답
                response = {
                    'task_id': task_id,
                    'status': 'success',
                    'hf_model_url': hf_model_url
                }
                
                status_dict[task_id] = {
                    'status': 'completed',
                    'progress': 100,
                    'message': '파인튜닝 완료',
                    'hf_model_url': hf_model_url
                }
                
                logger.info(f"✅ 파인튜닝 완료: {task_id}")
                
            except RuntimeError as e:
                error_str = str(e)
                if "out of memory" in error_str.lower() or "cuda out of memory" in error_str.lower():
                    logger.error(f"❌ GPU 메모리 부족으로 파인튜닝 실패: {e}")
                    
                    # GPU 메모리 상태 출력
                    if torch.cuda.is_available():
                        logger.error(f"📊 GPU 메모리 상태:")
                        logger.error(f"  - 할당된 메모리: {torch.cuda.memory_allocated() / 1024**3:.2f}GB")
                        logger.error(f"  - 예약된 메모리: {torch.cuda.memory_reserved() / 1024**3:.2f}GB")
                        logger.error(f"  - 최대 할당 메모리: {torch.cuda.max_memory_allocated() / 1024**3:.2f}GB")
                    
                    error_message = f"GPU 메모리 부족: {error_str}\n\n해결 방법:\n1. batch_size를 1로 설정\n2. LoRA rank를 4 이하로 설정\n3. max_length를 512로 제한\n4. 더 큰 GPU 사용"
                else:
                    logger.error(f"❌ 파인튜닝 실패: {e}")
                    logger.error(traceback.format_exc())
                    error_message = str(e)
                
                response = {
                    'task_id': task_id,
                    'status': 'error',
                    'error': error_message
                }
                
                status_dict[task_id] = {
                    'status': 'failed',
                    'progress': 0,
                    'message': f'파인튜닝 실패: {error_message}'
                }
            except Exception as e:
                logger.error(f"❌ 파인튜닝 실패: {e}")
                logger.error(traceback.format_exc())
                
                response = {
                    'task_id': task_id,
                    'status': 'error',
                    'error': str(e)
                }
                
                status_dict[task_id] = {
                    'status': 'failed',
                    'progress': 0,
                    'message': f'파인튜닝 실패: {str(e)}'
                }
            
            # 응답 전송
            response_queue.put(response)
            
            # GPU 메모리 정리
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                import gc
                gc.collect()
            except:
                pass
                
        except Exception as e:
            logger.error(f"❌ 워커 프로세스 오류: {e}")
            logger.error(traceback.format_exc())

def initialize_finetuning_multiprocessing():
    """파인튜닝 멀티프로세싱 초기화"""
    global finetuning_process, finetuning_request_queue, finetuning_response_queue, finetuning_status_dict
    
    if finetuning_process is not None:
        logger.info("파인튜닝 멀티프로세싱이 이미 실행 중입니다.")
        return
    
    # 멀티프로세싱 시작 방식 설정
    if mp.get_start_method(allow_none=True) != 'spawn':
        mp.set_start_method('spawn', force=True)
    
    # Manager로 공유 dict 생성
    manager = mp.Manager()
    finetuning_status_dict = manager.dict()
    
    # 큐 생성
    finetuning_request_queue = mp.Queue(maxsize=100)
    finetuning_response_queue = mp.Queue(maxsize=100)
    
    # 프로세스 시작
    finetuning_process = mp.Process(
        target=finetuning_worker_process,
        args=(finetuning_request_queue, finetuning_response_queue, finetuning_status_dict)
    )
    finetuning_process.start()
    
    logger.info("✅ 파인튜닝 멀티프로세싱 환경 초기화 완료")

async def submit_finetuning_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """파인튜닝 작업 제출"""
    global finetuning_request_queue, finetuning_response_queue, finetuning_status_dict
    
    if finetuning_process is None:
        initialize_finetuning_multiprocessing()
    
    # 요청 전송
    finetuning_request_queue.put(task_data)
    
    # 비동기적으로 응답 대기
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, finetuning_response_queue.get)
    
    return response

def get_finetuning_status(task_id: str) -> Optional[Dict[str, Any]]:
    """파인튜닝 작업 상태 조회"""
    global finetuning_status_dict
    
    if finetuning_status_dict is None:
        return None
    
    return dict(finetuning_status_dict.get(task_id, {}))

def cleanup_finetuning_multiprocessing():
    """파인튜닝 멀티프로세싱 정리"""
    global finetuning_process, finetuning_request_queue
    
    if finetuning_process is not None:
        # 종료 신호 전송
        finetuning_request_queue.put(None)
        
        # 프로세스 종료 대기
        finetuning_process.join(timeout=5)
        
        if finetuning_process.is_alive():
            finetuning_process.terminate()
            finetuning_process.join()
        
        logger.info("✅ 파인튜닝 멀티프로세싱 정리 완료")