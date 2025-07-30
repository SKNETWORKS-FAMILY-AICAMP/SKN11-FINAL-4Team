import torch
import torch.nn as nn
import torch.nn.functional as F


def find_multiple(n: int, k: int) -> int:
    if k == 0 or n % k == 0:
        return n
    return n + k - (n % k)


def pad_weight_(w: nn.Embedding | nn.Linear, multiple: int):
    """Pad the weight of an embedding or linear layer to a multiple of `multiple`."""
    if isinstance(w, nn.Embedding):
        # Pad input dim
        if w.weight.shape[1] % multiple == 0:
            return
        w.weight.data = F.pad(w.weight.data, (0, 0, 0, w.weight.shape[1] % multiple))
        w.num_embeddings, w.embedding_dim = w.weight.shape
    elif isinstance(w, nn.Linear):
        # Pad output dim
        if w.weight.shape[0] % multiple == 0:
            return
        w.weight.data = F.pad(w.weight.data, (0, 0, 0, w.weight.shape[0] % multiple))
        w.out_features, w.in_features = w.weight.shape
    else:
        raise ValueError(f"Unsupported weight type: {type(w)}")


def get_device() -> torch.device:
    import os
    
    if torch.cuda.is_available():
        # 환경 변수에서 TTS GPU ID 가져오기 (기본값: 0)
        tts_gpu_id = int(os.getenv('TTS_GPU_ID', '0'))
        
        # GPU가 존재하는지 확인
        if tts_gpu_id < torch.cuda.device_count():
            torch.cuda.set_device(tts_gpu_id)
            return torch.device(f"cuda:{tts_gpu_id}")
        else:
            # 지정된 GPU가 없으면 첫 번째 GPU 사용
            print(f"Warning: GPU {tts_gpu_id} not found. Using GPU 0.")
            torch.cuda.set_device(0)
            return torch.device("cuda:0")
    # MPS breaks for whatever reason. Uncomment when it's working.
    # if torch.mps.is_available():
    #     return torch.device("mps")
    return torch.device("cpu")


DEFAULT_DEVICE = get_device()
