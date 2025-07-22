"""
GPU Manager for dynamic memory allocation and monitoring
"""
import asyncio
import logging
import torch
from typing import Optional, Dict, Any
import subprocess

logger = logging.getLogger(__name__)


class GPUManager:
    """Manages GPU memory allocation dynamically"""
    
    def __init__(self):
        self.gpu_available = torch.cuda.is_available()
        self.gpu_count = torch.cuda.device_count() if self.gpu_available else 0
        self._lock = asyncio.Lock()
        
    async def get_gpu_memory_info(self, device_id: int = 0) -> Dict[str, int]:
        """Get GPU memory information for a specific device"""
        try:
            if not self.gpu_available or device_id >= self.gpu_count:
                return {"total": 0, "free": 0, "used": 0}
            
            # Get memory info using nvidia-smi
            process = await asyncio.create_subprocess_shell(
                f"nvidia-smi --query-gpu=memory.total,memory.free,memory.used --format=csv,noheader,nounits -i {device_id}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"nvidia-smi error: {stderr.decode().strip()}")
                return {"total": 0, "free": 0, "used": 0}
            
            # Parse output
            output = stdout.decode().strip()
            total, free, used = map(int, output.split(', '))
            
            return {
                "total": total,
                "free": free,
                "used": used,
                "utilization": (used / total) * 100 if total > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting GPU memory info: {e}")
            return {"total": 0, "free": 0, "used": 0}
    
    async def calculate_optimal_memory_fraction(self, 
                                              device_id: int = 0,
                                              reserve_mb: int = 2048,
                                              max_fraction: float = 0.9) -> float:
        """
        Calculate optimal GPU memory fraction based on available memory
        
        Args:
            device_id: GPU device ID
            reserve_mb: Memory to reserve for other processes (MB)
            max_fraction: Maximum fraction to use (safety limit)
            
        Returns:
            Optimal memory fraction between 0.3 and max_fraction
        """
        async with self._lock:
            memory_info = await self.get_gpu_memory_info(device_id)
            
            if memory_info["total"] == 0:
                logger.warning("No GPU memory available, using default fraction")
                return 0.5
            
            # Calculate available memory for our use
            available_for_use = memory_info["free"] - reserve_mb
            
            if available_for_use <= 0:
                logger.warning("Insufficient GPU memory, using minimum fraction")
                return 0.3
            
            # Calculate fraction
            optimal_fraction = available_for_use / memory_info["total"]
            
            # Clamp between 0.3 and max_fraction
            optimal_fraction = max(0.3, min(optimal_fraction, max_fraction))
            
            logger.info(f"GPU {device_id} Memory - Total: {memory_info['total']}MB, "
                       f"Free: {memory_info['free']}MB, "
                       f"Optimal fraction: {optimal_fraction:.2f}")
            
            return optimal_fraction
    
    async def monitor_memory_usage(self, interval_seconds: int = 60):
        """Continuously monitor GPU memory usage"""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                
                for device_id in range(self.gpu_count):
                    memory_info = await self.get_gpu_memory_info(device_id)
                    
                    if memory_info["total"] > 0:
                        logger.info(f"GPU {device_id} Memory Usage: "
                                   f"{memory_info['used']}MB / {memory_info['total']}MB "
                                   f"({memory_info['utilization']:.1f}%)")
                        
                        # Warning if memory usage is high
                        if memory_info['utilization'] > 90:
                            logger.warning(f"High GPU memory usage on device {device_id}: "
                                         f"{memory_info['utilization']:.1f}%")
                            
            except Exception as e:
                logger.error(f"Error monitoring GPU memory: {e}")
    
    async def get_all_gpus_info(self) -> Dict[int, Dict[str, int]]:
        """Get memory info for all available GPUs"""
        gpu_info = {}
        
        for device_id in range(self.gpu_count):
            gpu_info[device_id] = await self.get_gpu_memory_info(device_id)
            
        return gpu_info
    
    def get_least_utilized_gpu(self, gpu_info: Dict[int, Dict[str, int]]) -> int:
        """Find the GPU with lowest memory utilization"""
        if not gpu_info:
            return 0
            
        least_utilized = min(
            gpu_info.items(),
            key=lambda x: x[1].get('utilization', 100)
        )
        
        return least_utilized[0]


# Global GPU manager instance
_gpu_manager: Optional[GPUManager] = None
_gpu_manager_lock = asyncio.Lock()


async def get_gpu_manager() -> GPUManager:
    """Get or create GPU manager instance (thread-safe)"""
    global _gpu_manager
    async with _gpu_manager_lock:
        if _gpu_manager is None:
            _gpu_manager = GPUManager()
            # Start monitoring task
            asyncio.create_task(_gpu_manager.monitor_memory_usage())
    return _gpu_manager