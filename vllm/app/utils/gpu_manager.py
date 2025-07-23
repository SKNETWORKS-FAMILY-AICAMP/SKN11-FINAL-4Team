"""
GPU Manager wrapper that delegates to PyTorch-based implementation
"""
from .torch_gpu_manager import get_torch_gpu_manager, TorchGPUManager

# Re-export the PyTorch-based GPU manager
GPUManager = TorchGPUManager
get_gpu_manager = get_torch_gpu_manager

# For backward compatibility, export the same interface
__all__ = ['GPUManager', 'get_gpu_manager']