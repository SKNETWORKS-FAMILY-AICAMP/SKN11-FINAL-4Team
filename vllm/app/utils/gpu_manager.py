"""
GPU Manager wrapper that provides async interface for PyTorch-based implementation
"""
import asyncio
from typing import Dict, Any, Optional
from .torch_gpu_manager import get_torch_gpu_manager, TorchGPUManager

class AsyncGPUManager:
    """Async wrapper for TorchGPUManager"""
    
    def __init__(self, torch_gpu_manager: TorchGPUManager):
        self._gpu_manager = torch_gpu_manager
        self.gpu_available = self._gpu_manager.gpu_available
        self.gpu_count = self._gpu_manager.gpu_count
        self.current_device = self._gpu_manager.current_device
    
    async def get_gpu_info(self, device_id: int = 0) -> Dict[str, Any]:
        """Async wrapper for get_gpu_info"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._gpu_manager.get_gpu_info, device_id)
    
    async def set_device(self, device_id: int) -> bool:
        """Async wrapper for set_device"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._gpu_manager.set_device, device_id)
    
    async def get_all_gpus_info(self) -> Dict[int, Dict[str, Any]]:
        """Async wrapper for get_all_gpus_info"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._gpu_manager.get_all_gpus_info)
    
    async def get_least_utilized_gpu(self) -> int:
        """Async wrapper for get_least_utilized_gpu"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._gpu_manager.get_least_utilized_gpu)
    
    async def clear_cache(self, device_id: Optional[int] = None):
        """Async wrapper for clear_cache"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._gpu_manager.clear_cache, device_id)
    
    async def calculate_optimal_memory_fraction(self, 
                                              device_id: int = 0,
                                              reserve_mb: int = 2048,
                                              max_fraction: float = 0.9) -> float:
        """Async wrapper for calculate_optimal_memory_fraction"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self._gpu_manager.calculate_optimal_memory_fraction,
            device_id,
            reserve_mb,
            max_fraction
        )

# Global async GPU manager instance
_async_gpu_manager: Optional[AsyncGPUManager] = None

async def get_gpu_manager() -> AsyncGPUManager:
    """Get or create async GPU manager instance"""
    global _async_gpu_manager
    if _async_gpu_manager is None:
        torch_manager = get_torch_gpu_manager()
        _async_gpu_manager = AsyncGPUManager(torch_manager)
    return _async_gpu_manager

# For backward compatibility
GPUManager = AsyncGPUManager

__all__ = ['GPUManager', 'get_gpu_manager']