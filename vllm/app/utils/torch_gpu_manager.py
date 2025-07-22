"""
PyTorch-based GPU Manager for dynamic memory allocation and monitoring
"""
import asyncio
import logging
import torch
from typing import Optional, Dict, Any, List
import psutil
import time

logger = logging.getLogger(__name__)


class TorchGPUManager:
    """Manages GPU memory allocation dynamically using PyTorch"""
    
    def __init__(self):
        self.gpu_available = torch.cuda.is_available()
        self.gpu_count = torch.cuda.device_count() if self.gpu_available else 0
        self._lock = asyncio.Lock()
        self._memory_cache = {}
        self._cache_ttl = 5  # Cache TTL in seconds
        
        # MPS (Apple Silicon) support
        self.mps_available = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
        
        logger.info(f"🖥️ GPU Manager initialized - CUDA: {self.gpu_available}, "
                   f"GPU Count: {self.gpu_count}, MPS: {self.mps_available}")
        
    async def get_gpu_info(self, device_id: int = 0) -> Dict[str, Any]:
        """Get comprehensive GPU information for a specific device"""
        try:
            if not self.gpu_available or device_id >= self.gpu_count:
                return {
                    "available": False,
                    "name": "N/A",
                    "total": 0,
                    "free": 0,
                    "used": 0,
                    "allocated": 0,
                    "reserved": 0,
                    "utilization": 0,
                    "temperature": 0,
                    "power_draw": 0,
                    "compute_capability": "N/A"
                }
            
            # Check cache
            cache_key = f"gpu_{device_id}"
            current_time = time.time()
            
            if cache_key in self._memory_cache:
                cached_data, cache_time = self._memory_cache[cache_key]
                if current_time - cache_time < self._cache_ttl:
                    return cached_data
            
            # Get device properties
            device = torch.cuda.device(device_id)
            props = torch.cuda.get_device_properties(device_id)
            
            # Memory information
            memory_total = props.total_memory
            memory_allocated = torch.cuda.memory_allocated(device_id)
            memory_reserved = torch.cuda.memory_reserved(device_id)
            memory_free = memory_total - memory_reserved
            memory_used = memory_reserved  # Reserved memory is effectively "used"
            
            # GPU utilization (if available)
            utilization = 0
            temperature = 0
            power_draw = 0
            
            try:
                # Try to get utilization using torch
                if hasattr(torch.cuda, 'utilization'):
                    utilization = torch.cuda.utilization(device_id)
            except:
                # Fallback: estimate based on memory usage
                utilization = (memory_used / memory_total) * 100 if memory_total > 0 else 0
            
            gpu_info = {
                "available": True,
                "name": torch.cuda.get_device_name(device_id),
                "total": memory_total // (1024 * 1024),  # Convert to MB
                "free": memory_free // (1024 * 1024),
                "used": memory_used // (1024 * 1024),
                "allocated": memory_allocated // (1024 * 1024),
                "reserved": memory_reserved // (1024 * 1024),
                "utilization": utilization,
                "temperature": temperature,
                "power_draw": power_draw,
                "compute_capability": f"{props.major}.{props.minor}",
                "multi_processor_count": props.multi_processor_count,
                "max_threads_per_block": props.max_threads_per_block
            }
            
            # Update cache
            self._memory_cache[cache_key] = (gpu_info, current_time)
            
            return gpu_info
            
        except Exception as e:
            logger.error(f"Error getting GPU info for device {device_id}: {e}")
            return {
                "available": False,
                "name": "Error",
                "total": 0,
                "free": 0,
                "used": 0,
                "allocated": 0,
                "reserved": 0,
                "utilization": 0,
                "error": str(e)
            }
    
    async def get_gpu_memory_info(self, device_id: int = 0) -> Dict[str, int]:
        """Get GPU memory information (compatibility method)"""
        gpu_info = await self.get_gpu_info(device_id)
        return {
            "total": gpu_info["total"],
            "free": gpu_info["free"],
            "used": gpu_info["used"],
            "utilization": gpu_info["utilization"]
        }
    
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
            gpu_info = await self.get_gpu_info(device_id)
            
            if not gpu_info["available"] or gpu_info["total"] == 0:
                logger.warning("No GPU memory available, using default fraction")
                return 0.5
            
            # Calculate available memory for our use
            available_for_use = gpu_info["free"] - reserve_mb
            
            if available_for_use <= 0:
                logger.warning("Insufficient GPU memory, using minimum fraction")
                return 0.3
            
            # Calculate fraction
            optimal_fraction = available_for_use / gpu_info["total"]
            
            # Clamp between 0.3 and max_fraction
            optimal_fraction = max(0.3, min(optimal_fraction, max_fraction))
            
            logger.info(f"GPU {device_id} ({gpu_info['name']}) Memory - "
                       f"Total: {gpu_info['total']}MB, Free: {gpu_info['free']}MB, "
                       f"Allocated: {gpu_info['allocated']}MB, "
                       f"Optimal fraction: {optimal_fraction:.2f}")
            
            return optimal_fraction
    
    async def monitor_memory_usage(self, interval_seconds: int = 60):
        """Continuously monitor GPU memory usage"""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                
                for device_id in range(self.gpu_count):
                    gpu_info = await self.get_gpu_info(device_id)
                    
                    if gpu_info["available"]:
                        logger.info(f"GPU {device_id} ({gpu_info['name']}) Usage: "
                                   f"Memory: {gpu_info['used']}MB / {gpu_info['total']}MB "
                                   f"({gpu_info['utilization']:.1f}%), "
                                   f"Allocated: {gpu_info['allocated']}MB, "
                                   f"Reserved: {gpu_info['reserved']}MB")
                        
                        # Warning if memory usage is high
                        if gpu_info['utilization'] > 90:
                            logger.warning(f"⚠️ High GPU memory usage on device {device_id}: "
                                         f"{gpu_info['utilization']:.1f}%")
                            
                            # Try to clear cache if needed
                            if gpu_info['utilization'] > 95:
                                await self.clear_gpu_cache(device_id)
                                
            except Exception as e:
                logger.error(f"Error monitoring GPU memory: {e}")
    
    async def get_all_gpus_info(self) -> Dict[int, Dict[str, Any]]:
        """Get comprehensive info for all available GPUs"""
        gpu_info = {}
        
        for device_id in range(self.gpu_count):
            gpu_info[device_id] = await self.get_gpu_info(device_id)
            
        return gpu_info
    
    def get_least_utilized_gpu(self, gpu_info: Dict[int, Dict[str, Any]]) -> int:
        """Find the GPU with lowest memory utilization"""
        if not gpu_info:
            return 0
            
        # Filter out unavailable GPUs
        available_gpus = {k: v for k, v in gpu_info.items() if v.get('available', False)}
        
        if not available_gpus:
            return 0
            
        least_utilized = min(
            available_gpus.items(),
            key=lambda x: x[1].get('utilization', 100)
        )
        
        return least_utilized[0]
    
    async def clear_gpu_cache(self, device_id: Optional[int] = None):
        """Clear GPU cache to free up memory"""
        try:
            if device_id is not None:
                torch.cuda.set_device(device_id)
                torch.cuda.empty_cache()
                torch.cuda.synchronize(device_id)
                logger.info(f"✅ Cleared GPU {device_id} cache")
            else:
                # Clear cache for all GPUs
                for i in range(self.gpu_count):
                    torch.cuda.set_device(i)
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize(i)
                logger.info("✅ Cleared all GPU caches")
                
        except Exception as e:
            logger.error(f"Error clearing GPU cache: {e}")
    
    async def test_gpu_tensor(self, device_id: int = 0, size: int = 1000) -> bool:
        """Test GPU by creating and computing tensors"""
        try:
            if not self.gpu_available or device_id >= self.gpu_count:
                return False
                
            device = torch.device(f'cuda:{device_id}')
            
            # Create tensors
            x = torch.randn(size, size).to(device)
            y = torch.randn(size, size).to(device)
            
            # Perform computation
            z = torch.mm(x, y)
            
            # Wait for computation to complete
            torch.cuda.synchronize(device_id)
            
            logger.info(f"✅ GPU {device_id} tensor test successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ GPU {device_id} tensor test failed: {e}")
            return False
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information including CPU and memory"""
        return {
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_total": psutil.virtual_memory().total // (1024 * 1024 * 1024),  # GB
            "memory_available": psutil.virtual_memory().available // (1024 * 1024 * 1024),  # GB
            "memory_percent": psutil.virtual_memory().percent,
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda if self.gpu_available else "N/A",
            "cudnn_version": torch.backends.cudnn.version() if self.gpu_available else "N/A"
        }
    
    async def get_optimal_batch_size(self, device_id: int = 0, model_size_mb: int = 1000) -> int:
        """Calculate optimal batch size based on available GPU memory"""
        gpu_info = await self.get_gpu_info(device_id)
        
        if not gpu_info["available"]:
            return 1
            
        # Reserve 20% for overhead
        available_mb = gpu_info["free"] * 0.8
        
        # Estimate batch size (rough approximation)
        batch_size = max(1, int(available_mb / model_size_mb))
        
        logger.info(f"Recommended batch size for GPU {device_id}: {batch_size}")
        return batch_size


# Global GPU manager instance
_torch_gpu_manager: Optional[TorchGPUManager] = None
_torch_gpu_manager_lock = asyncio.Lock()


async def get_torch_gpu_manager() -> TorchGPUManager:
    """Get or create GPU manager instance (thread-safe)"""
    global _torch_gpu_manager
    async with _torch_gpu_manager_lock:
        if _torch_gpu_manager is None:
            _torch_gpu_manager = TorchGPUManager()
            # Start monitoring task
            asyncio.create_task(_torch_gpu_manager.monitor_memory_usage())
            
            # Initial GPU test
            if _torch_gpu_manager.gpu_available:
                for i in range(_torch_gpu_manager.gpu_count):
                    await _torch_gpu_manager.test_gpu_tensor(i, size=100)
                    
    return _torch_gpu_manager