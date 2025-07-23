"""
PyTorch-based GPU Manager for GPU information and device management
"""
import logging
import torch
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TorchGPUManager:    
    def __init__(self):
        self.gpu_available = torch.cuda.is_available()
        self.gpu_count = torch.cuda.device_count() if self.gpu_available else 0
        self.current_device = torch.cuda.current_device() if self.gpu_available else -1
        
        logger.info(f"🖥️ GPU Manager initialized - CUDA: {self.gpu_available}, "
                   f"GPU Count: {self.gpu_count}")
        
    def get_gpu_info(self, device_id: int = 0) -> Dict[str, Any]:
        """Get GPU information for the specified device"""
        try:
            if not self.gpu_available or device_id >= self.gpu_count:
                logger.error(f"GPU {device_id} is not available")
                return {
                    "available": False,
                    "name": "N/A",
                    "total": 0,
                    "free": 0,
                    "used": 0,
                    "compute_capability": "N/A"
                }
            
            # Get device properties
            props = torch.cuda.get_device_properties(device_id)
            
            # Memory information
            memory_total = props.total_memory
            memory_allocated = torch.cuda.memory_allocated(device_id)
            memory_reserved = torch.cuda.memory_reserved(device_id)
            memory_free = memory_total - memory_reserved
            memory_used = memory_reserved  # Reserved memory is effectively "used"
            
            gpu_info = {
                "available": True,
                "name": torch.cuda.get_device_name(device_id),
                "total": memory_total // (1024 * 1024),  # Convert to MB
                "free": memory_free // (1024 * 1024),
                "used": memory_used // (1024 * 1024),
                "allocated": memory_allocated // (1024 * 1024),
                "reserved": memory_reserved // (1024 * 1024),
                "compute_capability": f"{props.major}.{props.minor}",
            }
            
            return gpu_info
            
        except Exception as e:
            logger.error(f"Error getting GPU info for device {device_id}: {e}")
            return {
                "available": False,
                "name": "Error",
                "total": 0,
                "free": 0,
                "used": 0,
                "error": str(e)
            }
    
    def set_device(self, device_id: int) -> bool:
        """Set the current CUDA device"""
        try:
            if not self.gpu_available or device_id >= self.gpu_count:
                logger.error(f"Cannot set GPU {device_id} - not available")
                return False
                
            torch.cuda.set_device(device_id)
            self.current_device = device_id
            logger.info(f"✅ Set current GPU device to {device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting GPU device {device_id}: {e}")
            return False
    
    def get_all_gpus_info(self) -> Dict[int, Dict[str, Any]]:
        """Get information for all available GPUs"""
        gpu_info = {}
        
        for device_id in range(self.gpu_count):
            gpu_info[device_id] = self.get_gpu_info(device_id)
            
        return gpu_info
    
    def get_least_utilized_gpu(self) -> int:
        """Find the GPU with most free memory"""
        if not self.gpu_available:
            return -1
            
        gpu_info = self.get_all_gpus_info()
        
        # Filter out unavailable GPUs
        available_gpus = {k: v for k, v in gpu_info.items() if v.get('available', False)}
        
        if not available_gpus:
            return 0
            
        # Sort by free memory (descending)
        least_utilized = max(
            available_gpus.items(),
            key=lambda x: x[1].get('free', 0)
        )
        
        return least_utilized[0]
    
    def clear_cache(self, device_id: Optional[int] = None):
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
    
    def calculate_optimal_memory_fraction(self, 
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
        gpu_info = self.get_gpu_info(device_id)
        
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
                   f"Optimal fraction: {optimal_fraction:.2f}")
        
        return optimal_fraction


# Global GPU manager instance
_torch_gpu_manager: Optional[TorchGPUManager] = None


def get_torch_gpu_manager() -> TorchGPUManager:
    """Get or create GPU manager instance"""
    global _torch_gpu_manager
    if _torch_gpu_manager is None:
        _torch_gpu_manager = TorchGPUManager()
    return _torch_gpu_manager