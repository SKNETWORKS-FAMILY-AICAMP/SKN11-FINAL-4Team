"""
GPU 관리 유틸리티
여유 있는 GPU를 찾아서 동적으로 할당하는 기능 제공
"""

import os
import subprocess
import json
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def get_gpu_info() -> List[Dict]:
    """
    모든 GPU의 상태 정보를 가져옴
    Returns:
        각 GPU의 정보를 담은 딕셔너리 리스트
    """
    try:
        # nvidia-smi를 사용하여 JSON 형식으로 GPU 정보 가져오기
        cmd = [
            "nvidia-smi",
            "--query-gpu=index,name,memory.used,memory.free,memory.total,utilization.gpu",
            "--format=csv,noheader,nounits"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        gpus = []
        for line in result.stdout.strip().split('\n'):
            parts = line.split(', ')
            if len(parts) >= 6:
                gpu_info = {
                    'index': int(parts[0]),
                    'name': parts[1],
                    'memory_used': int(parts[2]),
                    'memory_free': int(parts[3]),
                    'memory_total': int(parts[4]),
                    'utilization': int(parts[5])
                }
                gpus.append(gpu_info)
        
        return gpus
        
    except subprocess.CalledProcessError as e:
        logger.error(f"nvidia-smi 실행 실패: {e}")
        return []
    except Exception as e:
        logger.error(f"GPU 정보 가져오기 실패: {e}")
        return []


def find_available_gpu(min_memory_mb: int = 10240, max_utilization: int = 50) -> Optional[int]:
    """
    파인튜닝에 사용 가능한 GPU를 찾음
    
    Args:
        min_memory_mb: 최소 필요 메모리 (MB)
        max_utilization: 최대 허용 GPU 사용률 (%)
    
    Returns:
        사용 가능한 GPU 인덱스, 없으면 None
    """
    gpus = get_gpu_info()
    
    if not gpus:
        logger.warning("GPU 정보를 가져올 수 없습니다")
        return None
    
    # vLLM이 사용 중인 GPU 확인
    # VLLM_GPU_IDS 환경변수에서 읽거나 기본값 0 사용
    vllm_gpu_ids = os.environ.get('VLLM_GPU_IDS', '0').split(',')
    vllm_gpus = [int(gpu_id.strip()) for gpu_id in vllm_gpu_ids if gpu_id.strip()]
    
    logger.info(f"vLLM이 사용 중인 GPU: {vllm_gpus}")
    
    # 메모리가 가장 많이 남은 GPU 찾기
    best_gpu = None
    max_free_memory = 0
    
    for gpu in gpus:
        # vLLM이 사용 중인 GPU는 제외
        if gpu['index'] in vllm_gpus:
            logger.info(f"GPU {gpu['index']}는 vLLM이 사용 중이므로 제외")
            continue
        
        # 조건 확인
        if (gpu['memory_free'] >= min_memory_mb and 
            gpu['utilization'] <= max_utilization):
            
            if gpu['memory_free'] > max_free_memory:
                max_free_memory = gpu['memory_free']
                best_gpu = gpu['index']
    
    if best_gpu is not None:
        logger.info(f"파인튜닝에 GPU {best_gpu} 선택 (여유 메모리: {max_free_memory}MB)")
    else:
        logger.warning("파인튜닝에 적합한 GPU를 찾을 수 없습니다")
    
    return best_gpu


def get_cuda_visible_devices(gpu_indices: List[int]) -> str:
    """
    GPU 인덱스 리스트를 CUDA_VISIBLE_DEVICES 문자열로 변환
    
    Args:
        gpu_indices: GPU 인덱스 리스트
    
    Returns:
        CUDA_VISIBLE_DEVICES 환경변수 값
    """
    return ','.join(map(str, gpu_indices))


def allocate_gpus_for_finetuning(num_gpus: int = 1, min_memory_mb: int = 10240) -> Optional[List[int]]:
    """
    파인튜닝을 위해 여러 개의 GPU를 할당
    
    Args:
        num_gpus: 필요한 GPU 개수
        min_memory_mb: GPU당 최소 필요 메모리
    
    Returns:
        할당된 GPU 인덱스 리스트, 실패시 None
    """
    gpus = get_gpu_info()
    
    if not gpus:
        return None
    
    # vLLM이 사용 중인 GPU 확인
    vllm_gpu_ids = os.environ.get('VLLM_GPU_IDS', '0').split(',')
    vllm_gpus = [int(gpu_id.strip()) for gpu_id in vllm_gpu_ids if gpu_id.strip()]
    
    # 사용 가능한 GPU를 메모리 여유가 많은 순으로 정렬
    available_gpus = []
    for gpu in gpus:
        if gpu['index'] not in vllm_gpus and gpu['memory_free'] >= min_memory_mb:
            available_gpus.append(gpu)
    
    available_gpus.sort(key=lambda x: x['memory_free'], reverse=True)
    
    if len(available_gpus) < num_gpus:
        logger.warning(f"요청된 {num_gpus}개의 GPU를 할당할 수 없습니다. 사용 가능: {len(available_gpus)}개")
        return None
    
    # 상위 num_gpus개 선택
    selected_gpus = [gpu['index'] for gpu in available_gpus[:num_gpus]]
    
    logger.info(f"파인튜닝을 위해 GPU {selected_gpus} 할당")
    return selected_gpus


def log_gpu_status():
    """현재 모든 GPU 상태를 로깅"""
    gpus = get_gpu_info()
    
    if not gpus:
        logger.warning("GPU 상태를 확인할 수 없습니다")
        return
    
    logger.info("=== GPU 상태 ===")
    for gpu in gpus:
        logger.info(
            f"GPU {gpu['index']} ({gpu['name']}): "
            f"사용중 {gpu['memory_used']}MB / "
            f"여유 {gpu['memory_free']}MB / "
            f"전체 {gpu['memory_total']}MB, "
            f"사용률 {gpu['utilization']}%"
        )