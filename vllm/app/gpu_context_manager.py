"""
GPU 컨텍스트 매니저
각 프로세스가 독립적인 CUDA 컨텍스트를 갖도록 관리
"""

import os
import torch
import torch.multiprocessing as mp
import logging
from typing import Optional, Callable
import signal
import sys

logger = logging.getLogger(__name__)

# CUDA 컨텍스트 격리를 위한 설정
if mp.get_start_method(allow_none=True) != 'spawn':
    mp.set_start_method('spawn', force=True)

class GPUContextManager:
    """GPU 컨텍스트를 격리하여 관리하는 클래스"""
    
    def __init__(self, gpu_id: int, memory_fraction: float = 0.5):
        self.gpu_id = gpu_id
        self.memory_fraction = memory_fraction
        self.process = None
        
    def _setup_gpu_context(self):
        """GPU 컨텍스트 설정 (자식 프로세스에서 실행)"""
        # CUDA 초기화 전에 환경 변수 설정
        os.environ['CUDA_VISIBLE_DEVICES'] = str(self.gpu_id)
        
        # PyTorch CUDA 설정
        if torch.cuda.is_available():
            # 메모리 fraction 설정
            torch.cuda.set_per_process_memory_fraction(self.memory_fraction, device=0)
            
            # CUDA 컨텍스트 초기화
            torch.cuda.init()
            device = torch.device("cuda:0")  # 격리된 환경에서는 항상 0
            
            logger.info(f"✅ GPU 컨텍스트 초기화 완료")
            logger.info(f"📍 물리적 GPU {self.gpu_id} → 논리적 GPU 0")
            logger.info(f"💾 메모리 사용률: {self.memory_fraction * 100}%")
            logger.info(f"🔧 GPU 이름: {torch.cuda.get_device_name(0)}")
            
            return device
        else:
            logger.warning("⚠️ GPU를 사용할 수 없습니다.")
            return torch.device("cpu")
    
    def run_in_isolated_context(self, target_func: Callable, *args, **kwargs):
        """격리된 GPU 컨텍스트에서 함수 실행"""
        def wrapper():
            # GPU 컨텍스트 설정
            device = self._setup_gpu_context()
            
            # 대상 함수에 device 전달
            kwargs['device'] = device
            
            # 함수 실행
            try:
                return target_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"GPU 컨텍스트 실행 오류: {e}")
                raise
            finally:
                # GPU 메모리 정리
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        
        # 별도 프로세스에서 실행
        self.process = mp.Process(target=wrapper)
        self.process.start()
        
        return self.process
    
    def wait(self, timeout: Optional[float] = None):
        """프로세스 종료 대기"""
        if self.process:
            self.process.join(timeout)
            return self.process.exitcode
        return None
    
    def terminate(self):
        """프로세스 강제 종료"""
        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join()

class GPUProcessPool:
    """여러 GPU 프로세스를 관리하는 풀"""
    
    def __init__(self):
        self.processes = {}
        
    def create_process(self, name: str, gpu_id: int, memory_fraction: float, 
                      target_func: Callable, *args, **kwargs):
        """새 GPU 프로세스 생성"""
        if name in self.processes:
            raise ValueError(f"프로세스 '{name}'이 이미 존재합니다.")
        
        manager = GPUContextManager(gpu_id, memory_fraction)
        process = manager.run_in_isolated_context(target_func, *args, **kwargs)
        
        self.processes[name] = {
            'manager': manager,
            'process': process,
            'gpu_id': gpu_id
        }
        
        logger.info(f"✅ GPU 프로세스 '{name}' 생성 (GPU {gpu_id})")
        
        return process
    
    def get_process_info(self, name: str):
        """프로세스 정보 조회"""
        if name in self.processes:
            proc_info = self.processes[name]
            return {
                'name': name,
                'gpu_id': proc_info['gpu_id'],
                'is_alive': proc_info['process'].is_alive(),
                'pid': proc_info['process'].pid if proc_info['process'] else None
            }
        return None
    
    def terminate_process(self, name: str):
        """특정 프로세스 종료"""
        if name in self.processes:
            self.processes[name]['manager'].terminate()
            del self.processes[name]
            logger.info(f"✅ GPU 프로세스 '{name}' 종료")
    
    def terminate_all(self):
        """모든 프로세스 종료"""
        for name in list(self.processes.keys()):
            self.terminate_process(name)

# 전역 GPU 프로세스 풀
gpu_process_pool = GPUProcessPool()

def cleanup_handler(signum, frame):
    """시그널 핸들러 - 정리 작업"""
    logger.info("🛑 종료 시그널 받음. GPU 프로세스 정리 중...")
    gpu_process_pool.terminate_all()
    sys.exit(0)

# 시그널 핸들러 등록
signal.signal(signal.SIGINT, cleanup_handler)
signal.signal(signal.SIGTERM, cleanup_handler)