"""
RunPod Serverless Worker for vLLM Generation with LoRA
EXAONE 모델을 사용한 텍스트 생성 (LoRA 어댑터 지원)
"""
import os
import sys
import logging
import json
import torch
import traceback
from typing import Dict, Any, List, Optional, AsyncGenerator, Iterator
import asyncio
import uuid
import time
import threading
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed

import runpod
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest
from transformers import AutoTokenizer
from huggingface_hub import snapshot_download, hf_hub_download

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 전역 변수
llm_engine = None
tokenizer = None
loaded_adapters = {}
device = None

# 기본 설정
DEFAULT_MODEL = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
DEFAULT_SYSTEM_MESSAGE = "당신은 도움이 되는 AI 어시스턴트입니다."
LORA_ADAPTERS_BASE_PATH = os.environ.get("LORA_ADAPTERS_BASE_PATH", "/app/lora_adapters")

# Idle 상태 유지 설정
ENABLE_KEEP_ALIVE = os.environ.get("ENABLE_KEEP_ALIVE", "true").lower() == "true"
KEEP_ALIVE_INTERVAL = int(os.environ.get("KEEP_ALIVE_INTERVAL", "300"))  # 5분
KEEP_ALIVE_INFERENCE_INTERVAL = int(os.environ.get("KEEP_ALIVE_INFERENCE_INTERVAL", "3600"))  # 1시간
PRELOAD_MODEL = os.environ.get("PRELOAD_MODEL", "true").lower() == "true"

class MultiVLLMManager:
    """멀티 vLLM 요청 관리자"""
    
    def __init__(self, max_concurrent_requests=3, vram_threshold=0.85):
        self.max_concurrent_requests = max_concurrent_requests
        self.vram_threshold = vram_threshold
        self.request_queue = Queue()
        self.active_requests = {}
        self.request_results = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_requests)
        self.running = True
        
        # 스케줄러 스레드 시작
        self.scheduler_thread = threading.Thread(target=self._request_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info(f"🔧 멀티 vLLM 매니저 초기화 - 최대 동시 요청: {max_concurrent_requests}, VRAM 임계값: {vram_threshold}")
    
    def get_vram_usage(self):
        """현재 VRAM 사용량 확인"""
        if torch.cuda.is_available():
            allocated_memory = torch.cuda.memory_allocated(0)
            total_memory = torch.cuda.get_device_properties(0).total_memory
            usage = allocated_memory / total_memory
            return usage
        return 0
    
    def can_process_new_request(self):
        """새 요청을 처리할 수 있는지 확인"""
        current_requests = len(self.active_requests)
        vram_usage = self.get_vram_usage()
        
        can_process = (current_requests < self.max_concurrent_requests and 
                      vram_usage < self.vram_threshold)
        
        if not can_process:
            logger.debug(f"📊 요청 처리 불가 - 현재 요청: {current_requests}/{self.max_concurrent_requests}, VRAM: {vram_usage:.1%}")
        
        return can_process
    
    def add_request(self, request_data):
        """요청을 큐에 추가"""
        request_id = request_data.get('request_id', f"req_{int(time.time())}")
        request_data['request_id'] = request_id
        
        self.request_queue.put(request_data)
        logger.info(f"📥 요청 추가됨 - ID: {request_id}, 큐 크기: {self.request_queue.qsize()}")
        
        return request_id
    
    def get_request_result(self, request_id, timeout=300):  # 5분 타임아웃
        """요청 결과 조회 (블로킹)"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.lock:
                if request_id in self.request_results:
                    result = self.request_results.pop(request_id)
                    logger.info(f"✅ 요청 결과 반환 - ID: {request_id}")
                    return result
            
            time.sleep(0.5)  # 0.5초마다 체크
        
        logger.error(f"⏰ 요청 타임아웃 - ID: {request_id}")
        return {"status": "timeout", "error": "요청이 시간 초과되었습니다."}
    
    def _execute_vllm_request(self, request_data):
        """개별 vLLM 요청 실행"""
        request_id = request_data['request_id']
        
        try:
            logger.info(f"🚀 vLLM 요청 처리 시작 - ID: {request_id}")
            
            # 실제 vLLM 생성 처리 (직접 처리 - 순환 참조 방지)
            result = self._process_single_request(request_data)
            
            logger.info(f"✅ vLLM 요청 완료 - ID: {request_id}")
            return result
            
        except Exception as e:
            error_msg = f"vLLM 요청 실행 중 오류: {str(e)}"
            logger.error(f"❌ [{request_id}] {error_msg}")
            logger.error(traceback.format_exc())
            
            return {
                "status": "failed",
                "request_id": request_id,
                "error": error_msg,
                "traceback": traceback.format_exc()
            }
        
        finally:
            # GPU 메모리 정리
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    
    def _process_single_request(self, request_data):
        """단일 요청 처리 (sync_handler 로직 복사)"""
        try:
            # 엔진 초기화 확인
            if llm_engine is None:
                model_name = request_data.get("model", DEFAULT_MODEL)
                initialize_engine(model_name)
            
            # 입력 검증
            job_input = validate_input(request_data)
            
            # LoRA 어댑터 처리
            lora_request = None
            if job_input["lora_adapter"]:
                adapter_info = job_input["lora_adapter"]
                logger.info(f"🔧 LoRA 어댑터가 요청에 포함됨 - 필수 처리 모드")
                
                try:
                    # 어댑터 정보 파싱
                    if isinstance(adapter_info, dict):
                        adapter_name = adapter_info.get("name", "custom_adapter")
                        adapter_path = adapter_info.get("path", adapter_name)
                    else:
                        adapter_path = str(adapter_info)
                        # hf:// 경로에서 어댑터 이름 추출
                        if adapter_path.startswith("hf://"):
                            # hf://username/model-name -> model-name을 어댑터 이름으로 사용
                            repo_parts = adapter_path.replace("hf://", "").split("/")
                            if len(repo_parts) >= 2:
                                adapter_name = repo_parts[-1]  # 모델 이름 부분
                            else:
                                adapter_name = adapter_path.replace("hf://", "")
                        else:
                            adapter_name = adapter_path
                    
                    logger.info(f"📋 어댑터 처리: name='{adapter_name}', path='{adapter_path}'")
                    
                    # 어댑터 로드
                    if adapter_name in loaded_adapters:
                        loaded_adapter = loaded_adapters[adapter_name]
                        logger.info(f"✅ 캐시된 어댑터 사용: {adapter_name}")
                    else:
                        # HF 토큰 가져오기
                        hf_token = job_input.get("hf_token")
                        if hf_token:
                            logger.info(f"🔑 HF 토큰 발견: {hf_token[:10]}...")
                        
                        # hf:// 경로라면 바로 로드
                        if adapter_path.startswith("hf://"):
                            loaded_adapter = load_lora_adapter(adapter_path, adapter_name, hf_token)
                        # UUID 형태라면 다양한 경로에서 찾기 시도
                        elif len(adapter_path) == 36 and adapter_path.count('-') == 4:
                            logger.warning(f"⚠️ UUID 형태의 어댑터 경로는 지원하지 않습니다: {adapter_path}")
                            logger.warning(f"   백엔드에서 HF repo 경로를 전달해야 합니다.")
                            raise FileNotFoundError(f"UUID 형태의 어댑터는 지원하지 않습니다. HF repo 경로를 사용하세요.")
                        else:
                            # 로컬 경로로 시도
                            loaded_adapter = load_lora_adapter(adapter_path, adapter_name, hf_token)
                    
                    # LoRA Request 생성
                    lora_request = LoRARequest(
                        lora_name=adapter_name,
                        lora_int_id=loaded_adapter["lora_int_id"],
                        lora_path=loaded_adapter["path"]
                    )
                    
                except Exception as e:
                    return {
                        "status": "failed",
                        "error": f"LoRA 어댑터를 찾을 수 없습니다: {adapter_name}",
                        "error_type": "adapter_not_found"
                    }
            
            # 샘플링 파라미터 설정
            sampling_params = SamplingParams(
                temperature=job_input["temperature"],
                max_tokens=job_input["max_tokens"],
                top_p=job_input["top_p"],
                top_k=job_input["top_k"],
                repetition_penalty=job_input["repetition_penalty"],
                stop=job_input["stop_sequences"],
                n=job_input["n"]
            )
            
            # 텍스트 생성
            results = generate_text(
                prompt=job_input["prompt"],
                sampling_params=sampling_params,
                lora_request=lora_request
            )
            
            # 응답 정리
            cleaned_results = [
                clean_response(result, job_input["influencer_name"])
                for result in results
            ]
            
            # 결과 생성
            result = {
                "status": "success",
                "generated_text": cleaned_results[0] if len(cleaned_results) == 1 else cleaned_results,
                "model": DEFAULT_MODEL,
                "used_lora": job_input["lora_adapter"] is not None,
                "temperature": job_input["temperature"],
                "max_tokens": job_input["max_tokens"],
                "num_generated": len(cleaned_results)
            }
            
            if job_input["lora_adapter"]:
                result["lora_adapter"] = adapter_name
            
            return result
            
        except Exception as e:
            return {
                "status": "failed",
                "error": f"생성 처리 중 오류 발생: {str(e)}",
                "traceback": traceback.format_exc()
            }
    
    def _request_scheduler(self):
        """요청 스케줄러 - 백그라운드에서 실행"""
        logger.info("🔄 vLLM 요청 스케줄러 시작")
        
        while self.running:
            try:
                # 새 요청 처리 가능한지 확인
                if self.can_process_new_request() and not self.request_queue.empty():
                    try:
                        request_data = self.request_queue.get_nowait()
                        request_id = request_data['request_id']
                        
                        # 요청 시작
                        future = self.executor.submit(self._execute_vllm_request, request_data)
                        
                        with self.lock:
                            self.active_requests[request_id] = future
                        
                        logger.info(f"🚀 요청 시작 - ID: {request_id}, 활성 요청: {len(self.active_requests)}")
                        
                        # 완료된 요청 확인 및 정리
                        self._cleanup_completed_requests()
                        
                    except Empty:
                        pass
                
                # 완료된 요청 정리
                self._cleanup_completed_requests()
                
                # VRAM 상태 로깅 (30초마다)
                if int(time.time()) % 30 == 0:
                    vram_usage = self.get_vram_usage()
                    active_requests = len(self.active_requests)
                    queue_size = self.request_queue.qsize()
                    logger.info(f"📊 vLLM 시스템 상태 - VRAM: {vram_usage:.1%}, 활성요청: {active_requests}, 대기요청: {queue_size}")
                
                time.sleep(1)  # 1초마다 체크
                
            except Exception as e:
                logger.error(f"❌ vLLM 스케줄러 오류: {e}")
                time.sleep(5)
    
    def _cleanup_completed_requests(self):
        """완료된 요청 정리"""
        completed_requests = []
        
        with self.lock:
            for request_id, future in list(self.active_requests.items()):
                if future.done():
                    try:
                        result = future.result()
                        self.request_results[request_id] = result
                        completed_requests.append(request_id)
                        logger.info(f"✅ 요청 완료 - ID: {request_id}, 상태: {result.get('status', 'unknown')}")
                    except Exception as e:
                        error_result = {
                            "status": "failed",
                            "request_id": request_id,
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        }
                        self.request_results[request_id] = error_result
                        completed_requests.append(request_id)
                        logger.error(f"❌ 요청 실행 중 오류 - ID: {request_id}, 오류: {e}")
            
            # 완료된 요청 제거
            for request_id in completed_requests:
                self.active_requests.pop(request_id, None)
    
    def get_status(self):
        """현재 매니저 상태 반환"""
        return {
            "active_requests": len(self.active_requests),
            "queued_requests": self.request_queue.qsize(),
            "vram_usage": self.get_vram_usage(),
            "max_concurrent": self.max_concurrent_requests
        }
    
    def shutdown(self):
        """매니저 종료"""
        logger.info("🛑 멀티 vLLM 매니저 종료 중...")
        self.running = False
        self.executor.shutdown(wait=True)

# 전역 매니저 인스턴스
vllm_manager = None

def get_vllm_manager():
    """vLLM 매니저 인스턴스 반환 (싱글톤)"""
    global vllm_manager
    if vllm_manager is None:
        # GPU 메모리에 따라 최대 동시 요청 수 결정
        if torch.cuda.is_available():
            total_vram = torch.cuda.get_device_properties(0).total_memory / 1e9
            if total_vram >= 80:  # H100
                max_requests = 8
            elif total_vram >= 40:  # A100
                max_requests = 6
            elif total_vram >= 24:  # RTX 4090
                max_requests = 4
            else:
                max_requests = 2
        else:
            max_requests = 1
        
        vllm_manager = MultiVLLMManager(max_concurrent_requests=max_requests, vram_threshold=0.85)
        logger.info(f"🔧 vLLM 매니저 생성됨 - 최대 동시 요청: {max_requests}")
    
    return vllm_manager

def initialize_engine(model_name: str = DEFAULT_MODEL):
    """vLLM 엔진 초기화 (GPU 상태 상세 로깅)"""
    global llm_engine, tokenizer, device
    
    if llm_engine is not None:
        logger.info("✅ 엔진이 이미 초기화되어 있습니다.")
        return
    
    logger.info(f"🔧 vLLM 엔진 초기화 시작: {model_name}")
    
    # GPU 상태 상세 확인
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / 1e9
        gpu_memory_allocated = torch.cuda.memory_allocated(0) / 1e9
        gpu_memory_cached = torch.cuda.memory_reserved(0) / 1e9
        
        logger.info(f"🖥️ GPU 디바이스: {gpu_name}")
        logger.info(f"📊 GPU 메모리 총량: {gpu_memory_total:.2f} GB")
        logger.info(f"📊 GPU 메모리 할당: {gpu_memory_allocated:.2f} GB")
        logger.info(f"📊 GPU 메모리 예약: {gpu_memory_cached:.2f} GB")
        logger.info(f"📊 GPU 사용 가능: {gpu_memory_total - gpu_memory_allocated:.2f} GB")
        
        # CUDA 버전 정보
        logger.info(f"🔧 CUDA 버전: {torch.version.cuda}")
        logger.info(f"🔧 PyTorch 버전: {torch.__version__}")
        
        gpu_memory_utilization = 0.85  # 안전하게 85%로 설정
        logger.info(f"⚙️ GPU 메모리 사용률 제한: {gpu_memory_utilization * 100}%")
    else:
        device = torch.device("cpu")
        logger.error("❌ CUDA를 사용할 수 없습니다!")
        logger.error("❌ vLLM은 GPU가 필요합니다. CPU 모드는 지원되지 않습니다.")
        
        # CPU 정보
        import os
        cpu_count = os.cpu_count()
        logger.info(f"💻 CPU 코어 수: {cpu_count}")
        
        gpu_memory_utilization = 0
        
        # GPU 없이는 vLLM 실행 불가
        raise RuntimeError("vLLM은 GPU가 필요합니다. CUDA 환경을 확인하세요.")
    
    try:
        # 토크나이저 로드
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # vLLM 엔진 초기화 (CPU 사용량 최적화)
        llm_engine = LLM(
            model=model_name,
            tensor_parallel_size=1,
            trust_remote_code=True,
            dtype="bfloat16" if torch.cuda.is_available() else "float32",
            enable_lora=True,
            max_lora_rank=64,
            max_loras=8,  # 더 많은 LoRA 슬롯
            gpu_memory_utilization=gpu_memory_utilization,
            # CPU 최적화 설정
            max_model_len=2048,  # 최대 모델 길이 제한
            max_num_batched_tokens=4096,  # 배치 토큰 수 제한  
            max_num_seqs=64,  # 최대 시퀀스 수 제한
            disable_log_stats=True,  # 통계 로깅 비활성화
            enforce_eager=False,  # CUDA 그래프 사용
            # 추가 최적화
            block_size=16,  # 메모리 블록 크기
            swap_space=4  # 스왑 공간 (GB)
        )
        
        logger.info("✅ vLLM 엔진 초기화 완료")
        
    except Exception as e:
        logger.error(f"❌ 엔진 초기화 실패: {str(e)}")
        raise

def create_chat_prompt(
    user_message: str,
    system_message: str = DEFAULT_SYSTEM_MESSAGE,
    influencer_name: Optional[str] = None,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """채팅 프롬프트 생성"""
    messages = []
    
    # 시스템 메시지
    if influencer_name:
        system_message = f"당신은 {influencer_name}입니다. {system_message}"
    messages.append({"role": "system", "content": system_message})
    
    # 채팅 히스토리 추가
    if chat_history:
        for msg in chat_history:
            messages.append(msg)
    
    # 사용자 메시지
    messages.append({"role": "user", "content": user_message})
    
    # 토크나이저의 chat template 적용
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    return prompt

def download_lora_files(repo_id: str, cache_dir: str, hf_token: Optional[str] = None) -> str:
    """LoRA 어댑터 파일을 효율적으로 다운로드"""
    import os
    import subprocess
    
    # 캐시 경로 생성
    local_path = os.path.join(cache_dir, repo_id.replace("/", "--"))
    
    # 이미 다운로드되어 있는지 확인
    if os.path.exists(os.path.join(local_path, "adapter_config.json")):
        logger.info(f"✅ 캐시된 어댑터 사용: {local_path}")
        return local_path
    
    os.makedirs(local_path, exist_ok=True)
    
    # 방법 1: Git Clone 사용 (가장 빠름)
    try:
        # Git LFS 설치 확인
        subprocess.run(["git", "lfs", "install"], capture_output=True, check=True)
        
        # Git clone URL 구성
        if hf_token:
            # 토큰을 포함한 URL
            clone_url = f"https://oauth2:{hf_token}@huggingface.co/{repo_id}"
            logger.info(f"🔑 HuggingFace 토큰으로 인증된 Git clone 사용")
        else:
            clone_url = f"https://huggingface.co/{repo_id}"
        
        # GIT_LFS_SKIP_SMUDGE=1로 포인터만 다운로드 (LoRA는 작아서 괜찮음)
        env = os.environ.copy()
        env["GIT_LFS_SKIP_SMUDGE"] = "1"
        
        logger.info(f"🚀 Git clone 시작: {repo_id}")
        
        # sparse-checkout으로 필요한 파일만 다운로드
        cmd_clone = ["git", "clone", "--depth", "1", "--filter=blob:none", clone_url, local_path]
        result = subprocess.run(cmd_clone, env=env, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # sparse-checkout 설정
            subprocess.run(["git", "-C", local_path, "sparse-checkout", "init"], check=True)
            subprocess.run(["git", "-C", local_path, "sparse-checkout", "set", 
                          "adapter_config.json", "adapter_model.safetensors", "adapter_model.bin"], 
                          check=True)
            
            # LFS 파일 다운로드
            subprocess.run(["git", "-C", local_path, "lfs", "pull", "--include", 
                          "adapter_model.safetensors,adapter_model.bin"], 
                          check=True)
            
            logger.info(f"✅ Git clone 다운로드 성공")
            return local_path
        else:
            logger.warning(f"⚠️ Git clone 실패: {result.stderr}")
            
    except subprocess.CalledProcessError as e:
        logger.warning(f"⚠️ Git 명령 실패: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Git clone 오류: {e}")
    
    # 방법 2: HF CLI 사용
    try:
        # 환경 변수 설정
        env = os.environ.copy()
        if hf_token:
            env["HUGGING_FACE_HUB_TOKEN"] = hf_token
            logger.info(f"🔑 HuggingFace 토큰 사용")
        
        # hf download 명령어 구성
        cmd = [
            "huggingface-cli", "download",
            repo_id,
            "--local-dir", local_path,
            "--include", "adapter_config.json",
            "--include", "adapter_model.safetensors",
            "--include", "adapter_model.bin",
            "--quiet"
        ]
        
        if hf_token:
            cmd.extend(["--token", hf_token])
        
        logger.info(f"🚀 HF CLI로 다운로드 시작: {repo_id}")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            logger.info(f"✅ HF CLI 다운로드 성공")
            return local_path
        else:
            logger.warning(f"⚠️ HF CLI 다운로드 실패: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.warning("⚠️ HF CLI 다운로드 시간 초과")
    except FileNotFoundError:
        logger.warning("⚠️ huggingface-cli가 설치되지 않음, Python API 사용")
    except Exception as e:
        logger.warning(f"⚠️ HF CLI 다운로드 오류: {e}")
    
    # HF CLI 실패 시 Python API로 폴백
    logger.info("📥 Python API로 다운로드 시도")
    
    # 필수 파일 목록
    essential_files = [
        "adapter_config.json",
        "adapter_model.safetensors",
        "adapter_model.bin",  # 폴백
    ]
    
    download_kwargs = {}
    if hf_token:
        download_kwargs["token"] = hf_token
    
    # 필수 파일만 다운로드
    downloaded = False
    for filename in essential_files:
        try:
            logger.info(f"📥 다운로드 시도: {filename}")
            local_file = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                cache_dir=cache_dir,
                local_dir=local_path,
                **download_kwargs
            )
            logger.info(f"✅ 다운로드 성공: {filename}")
            
            # safetensors나 bin 파일 중 하나만 있으면 됨
            if filename.endswith((".safetensors", ".bin")):
                downloaded = True
                break
        except Exception as e:
            logger.debug(f"⚠️ {filename} 다운로드 실패: {e}")
            continue
    
    if not downloaded:
        # 모든 파일 다운로드 실패 시 전체 스냅샷 다운로드
        logger.warning("⚠️ 개별 파일 다운로드 실패, 전체 스냅샷 다운로드 시도")
        local_path = snapshot_download(repo_id, cache_dir=cache_dir, **download_kwargs)
    
    return local_path

def load_lora_adapter(adapter_path: str, adapter_name: str, hf_token: Optional[str] = None) -> Dict[str, Any]:
    """LoRA 어댑터 로드 (개선된 오류 처리)"""
    global loaded_adapters
    
    if adapter_name in loaded_adapters:
        logger.info(f"✅ 캐시된 어댑터 사용: {adapter_name}")
        return loaded_adapters[adapter_name]
    
    logger.info(f"🔄 LoRA 어댑터 로드 시작 - name: '{adapter_name}', path: '{adapter_path}'")
    
    try:
        # 경로 처리 개선
        if adapter_path.startswith("hf://"):
            # Hugging Face Hub에서 다운로드
            repo_id = adapter_path.replace("hf://", "")
            logger.info(f"📥 Hugging Face Hub에서 어댑터 다운로드: {repo_id}")
            
            # 효율적인 다운로드 사용
            local_path = download_lora_files(repo_id, "/app/lora_cache", hf_token)
        elif adapter_path.startswith("/"):
            # 절대 경로인 경우 그대로 사용
            local_path = adapter_path
            logger.info(f"📂 절대 경로 사용: {local_path}")
        elif os.path.exists(adapter_path):
            # 현재 디렉토리에서 직접 찾기
            local_path = adapter_path
            logger.info(f"📂 현재 경로에서 발견: {local_path}")
        else:
            # UUID 형태의 어댑터 이름인 경우 처리
            if len(adapter_path) == 36 and adapter_path.count('-') == 4:
                logger.warning(f"⚠️ UUID 형태의 어댑터 경로 감지: {adapter_path}")
                # 기본 경로에서 찾기 시도
                local_path = os.path.join(LORA_ADAPTERS_BASE_PATH, adapter_path)
                if not os.path.exists(local_path):
                    # UUID를 Hugging Face 형태로 변환 시도
                    potential_hf_path = f"hf://username/{adapter_name}"
                    logger.info(f"📥 HF 경로로 시도: {potential_hf_path}")
                    raise FileNotFoundError(f"UUID 형태의 어댑터를 찾을 수 없습니다. HF 경로를 사용하세요: {potential_hf_path}")
            else:
                # 상대 경로인 경우 기본 경로에서 찾기
                local_path = os.path.join(LORA_ADAPTERS_BASE_PATH, adapter_path)
                logger.info(f"📂 기본 경로에서 검색: {local_path}")
        
        # 경로 존재 확인
        if not os.path.exists(local_path):
            available_adapters = []
            if os.path.exists(LORA_ADAPTERS_BASE_PATH):
                available_adapters = os.listdir(LORA_ADAPTERS_BASE_PATH)
            
            error_msg = f"LoRA 어댑터 경로를 찾을 수 없습니다: {local_path}"
            if available_adapters:
                error_msg += f"\n사용 가능한 어댑터: {available_adapters}"
            else:
                error_msg += f"\n기본 어댑터 디렉토리가 비어있습니다: {LORA_ADAPTERS_BASE_PATH}"
            
            raise FileNotFoundError(error_msg)
        
        # adapter_config.json 파일 확인
        adapter_config_path = os.path.join(local_path, "adapter_config.json")
        if not os.path.exists(adapter_config_path):
            # 디렉토리 내용 확인
            dir_contents = os.listdir(local_path) if os.path.isdir(local_path) else ["(not a directory)"]
            raise FileNotFoundError(f"adapter_config.json 파일을 찾을 수 없습니다: {adapter_config_path}\n디렉토리 내용: {dir_contents}")
        
        # LoRA 어댑터 정보 생성
        adapter_info = {
            "name": adapter_name,
            "path": local_path,
            "lora_int_id": len(loaded_adapters) + 1,  # 고유 ID 할당
            "loaded_at": os.path.getmtime(local_path)
        }
        
        loaded_adapters[adapter_name] = adapter_info
        logger.info(f"✅ LoRA 어댑터 로드 완료: {adapter_name} (경로: {local_path})")
        
        return adapter_info
        
    except Exception as e:
        logger.error(f"❌ LoRA 어댑터 로드 실패: {str(e)}")
        raise

def validate_input(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """입력 데이터 검증"""
    # 필수 필드 확인
    if "prompt" not in job_input and "messages" not in job_input:
        raise ValueError("prompt 또는 messages 필드가 필요합니다.")
    
    validated = {
        # 프롬프트 관련
        "prompt": job_input.get("prompt"),
        "messages": job_input.get("messages"),
        "system_message": job_input.get("system_message", DEFAULT_SYSTEM_MESSAGE),
        "influencer_name": job_input.get("influencer_name"),
        
        # 생성 파라미터
        "temperature": float(job_input.get("temperature", 0.7)),
        "max_tokens": int(job_input.get("max_tokens", 512)),
        "top_p": float(job_input.get("top_p", 0.9)),
        "top_k": int(job_input.get("top_k", 50)),
        "repetition_penalty": float(job_input.get("repetition_penalty", 1.1)),
        "stop_sequences": job_input.get("stop_sequences", ["[|Human|", "[|System|", "<|im_end|>", "</s>", "<|eot_id|>"]),
        
        # LoRA 관련
        "lora_adapter": job_input.get("lora_adapter"),
        "hf_token": job_input.get("hf_token"),
        
        # 스트리밍
        "stream": job_input.get("stream", False),
        
        # 배치 처리
        "n": int(job_input.get("n", 1)),  # 생성할 응답 수
    }
    
    # 프롬프트 생성
    if validated["messages"]:
        # messages 형식인 경우
        validated["prompt"] = tokenizer.apply_chat_template(
            validated["messages"],
            tokenize=False,
            add_generation_prompt=True
        )
    elif not validated["prompt"]:
        # prompt가 없는 경우 에러
        raise ValueError("prompt 또는 messages 중 하나는 필수입니다.")
    else:
        # 일반 prompt인 경우 chat template 적용
        validated["prompt"] = create_chat_prompt(
            user_message=validated["prompt"],
            system_message=validated["system_message"],
            influencer_name=validated["influencer_name"]
        )
    
    return validated

def generate_text(
    prompt: str,
    sampling_params: SamplingParams,
    lora_request: Optional[LoRARequest] = None
) -> List[str]:
    """텍스트 생성 (동기)"""
    request_id = str(uuid.uuid4())
    
    # 생성 실행
    outputs = llm_engine.generate(
        prompts=[prompt],
        sampling_params=sampling_params,
        lora_request=lora_request
    )
    
    # 결과 추출
    results = []
    for output in outputs:
        for completion in output.outputs:
            results.append(completion.text)
    
    return results

def generate_text_stream(
    prompt: str,
    sampling_params: SamplingParams,
    lora_request: Optional[LoRARequest] = None
) -> Iterator[str]:
    """텍스트 생성 (스트리밍)"""
    request_id = str(uuid.uuid4())
    
    # vLLM의 스트리밍 생성
    for output in llm_engine.generate(
        prompts=[prompt],
        sampling_params=sampling_params,
        lora_request=lora_request,
        use_tqdm=False
    ):
        for completion in output.outputs:
            yield completion.text

def clean_response(response: str, influencer_name: Optional[str] = None) -> str:
    """응답 정리"""
    # 불필요한 마커 제거
    markers_to_remove = [
        "[|Assistant|]", "[|Human|]", "[|System|]",
        "<|im_start|>", "<|im_end|>", "<|eot_id|>",
        "</s>", "<s>", "assistant\n", "user\n", "system\n"
    ]
    
    cleaned = response
    for marker in markers_to_remove:
        cleaned = cleaned.replace(marker, "")
    
    # 인플루언서 이름 제거 (있는 경우)
    if influencer_name:
        cleaned = cleaned.replace(f"{influencer_name}:", "")
        cleaned = cleaned.replace(f"{influencer_name} :", "")
    
    # 앞뒤 공백 제거
    cleaned = cleaned.strip()
    
    return cleaned

def handler(job):
    """RunPod 핸들러 함수 (run 엔드포인트용 - 멀티 vLLM 지원)"""
    try:
        logger.info("📥 새로운 비동기 생성 요청 수신")
        
        # 멀티 vLLM 매니저 사용
        manager = get_vllm_manager()
        
        # 요청 데이터 준비
        request_data = job["input"].copy()
        request_id = manager.add_request(request_data)
        
        # 결과 대기 및 반환
        result = manager.get_request_result(request_id, timeout=300)
        
        # 멀티 처리 정보 추가
        if result.get("status") == "success":
            result["processing_info"] = {
                "request_id": request_id,
                "concurrent_processing": True,
                "manager_status": manager.get_status()
            }
        
        return result
        
    except Exception as e:
        logger.error(f"❌ 멀티 vLLM 핸들러 오류: {e}")
        # 실패 시 동기 처리로 폴백
        logger.info("🔄 동기 처리로 폴백")
        return sync_handler(job)

def sync_handler(job):
    """RunPod 동기 핸들러 함수 (runsync 엔드포인트용)"""
    try:
        logger.info("📥 새로운 동기 생성 요청 수신")
        
        # 엔진 초기화 확인
        if llm_engine is None:
            model_name = job["input"].get("model", DEFAULT_MODEL)
            initialize_engine(model_name)
        
        # 입력 검증
        job_input = validate_input(job["input"])
        
        # LoRA 어댑터 처리 (필수 어댑터 검증)
        lora_request = None
        if job_input["lora_adapter"]:
            adapter_info = job_input["lora_adapter"]
            logger.info(f"🔧 LoRA 어댑터가 요청에 포함됨 - 필수 처리 모드")
            
            try:
                # 어댑터 정보 파싱
                if isinstance(adapter_info, dict):
                    adapter_name = adapter_info.get("name", "custom_adapter")
                    adapter_path = adapter_info.get("path", adapter_name)
                else:
                    # 문자열인 경우
                    adapter_name = str(adapter_info)
                    adapter_path = str(adapter_info)
                
                logger.info(f"🔄 LoRA 어댑터 요청 - name: '{adapter_name}', path: '{adapter_path}'")
                
                # 1단계: 캐시에서 확인
                if adapter_name in loaded_adapters:
                    logger.info(f"✅ 캐시된 어댑터 사용: {adapter_name}")
                    loaded_adapter = loaded_adapters[adapter_name]
                else:
                    # 2단계: 어댑터 존재 여부 확인 및 로드 시도
                    logger.info(f"🔍 어댑터 존재 여부 확인 중: {adapter_name}")
                    
                    # UUID 형태라면 다양한 경로에서 찾기 시도
                    if len(adapter_path) == 36 and adapter_path.count('-') == 4:
                        logger.info(f"🔍 UUID 형태 어댑터 ID 감지: {adapter_path}")
                        
                        # 가능한 경로들 시도
                        possible_paths = [
                            adapter_path,  # 원본 그대로
                            os.path.join(LORA_ADAPTERS_BASE_PATH, adapter_path),  # 기본 디렉토리
                            f"hf://username/{adapter_path}",  # Hugging Face (일반적인 경우)
                            f"hf://user/{adapter_name}",  # 이름으로 시도
                        ]
                        
                        loaded_adapter = None
                        for attempt_path in possible_paths:
                            try:
                                logger.info(f"📂 시도 중: {attempt_path}")
                                loaded_adapter = load_lora_adapter(attempt_path, adapter_name)
                                logger.info(f"✅ 어댑터 로드 성공: {attempt_path}")
                                break
                            except Exception as path_error:
                                logger.debug(f"❌ 경로 실패: {attempt_path} - {path_error}")
                                continue
                        
                        if loaded_adapter is None:
                            raise FileNotFoundError(f"모든 경로에서 어댑터를 찾을 수 없습니다: {adapter_name}")
                    else:
                        # 일반적인 경로 처리
                        loaded_adapter = load_lora_adapter(adapter_path, adapter_name)
                
                # 3단계: LoRA Request 생성
                lora_request = LoRARequest(
                    lora_name=adapter_name,
                    lora_int_id=loaded_adapter["lora_int_id"],
                    lora_path=loaded_adapter["path"]
                )
                
                logger.info(f"✅ LoRA 어댑터 준비 완료: {adapter_name}")
                
            except Exception as e:
                logger.error(f"❌ LoRA 어댑터 로드 최종 실패: {e}")
                logger.error(f"❌ 필수 LoRA 어댑터 '{adapter_name}'을 찾을 수 없습니다")
                
                # LoRA 어댑터가 요청에 포함되었지만 찾을 수 없는 경우 에러 반환
                return {
                    "status": "failed",
                    "error": f"LoRA 어댑터를 찾을 수 없습니다: {adapter_name}",
                    "error_type": "adapter_not_found", 
                    "adapter_name": adapter_name,
                    "adapter_path": adapter_path,
                    "message": "요청된 LoRA 어댑터가 서버에 존재하지 않습니다. 어댑터 경로를 확인하거나 먼저 업로드해주세요.",
                    "suggestions": [
                        f"Hugging Face 형태로 시도: hf://username/{adapter_name}",
                        f"절대 경로로 시도: /app/lora_adapters/{adapter_name}",
                        "어댑터가 올바르게 업로드되었는지 확인"
                    ]
                }
        else:
            # LoRA 어댑터가 요청에 포함되지 않은 경우
            logger.info(f"📝 베이스 모델로 생성 - LoRA 어댑터 없음")
        
        # 샘플링 파라미터 설정
        sampling_params = SamplingParams(
            temperature=job_input["temperature"],
            max_tokens=job_input["max_tokens"],
            top_p=job_input["top_p"],
            top_k=job_input["top_k"],
            repetition_penalty=job_input["repetition_penalty"],
            stop=job_input["stop_sequences"],
            n=job_input["n"]
        )
        
        # 텍스트 생성
        logger.info("🚀 텍스트 생성 시작...")
        results = generate_text(
            prompt=job_input["prompt"],
            sampling_params=sampling_params,
            lora_request=lora_request
        )
        
        # 응답 정리
        cleaned_results = [
            clean_response(result, job_input["influencer_name"])
            for result in results
        ]
        
        # 결과 생성
        result = {
            "status": "success",
            "generated_text": cleaned_results[0] if len(cleaned_results) == 1 else cleaned_results,
            "model": DEFAULT_MODEL,
            "used_lora": job_input["lora_adapter"] is not None,
            "temperature": job_input["temperature"],
            "max_tokens": job_input["max_tokens"],
            "num_generated": len(cleaned_results)
        }
        
        if job_input["lora_adapter"]:
            result["lora_adapter"] = adapter_name
        
        logger.info(f"✅ 텍스트 생성 완료 (길이: {len(result['generated_text'])})")
        return result
        
    except Exception as e:
        error_msg = f"생성 처리 중 오류 발생: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(traceback.format_exc())
        
        return {
            "status": "failed",
            "error": error_msg,
            "traceback": traceback.format_exc()
        }

def batch_handler(jobs):
    """배치 처리 핸들러"""
    results = []
    
    # 엔진 초기화 확인
    if llm_engine is None:
        # 첫 번째 job의 모델 사용
        model_name = jobs[0]["input"].get("model", DEFAULT_MODEL) if jobs else DEFAULT_MODEL
        initialize_engine(model_name)
    
    # 모든 요청을 한 번에 처리
    all_prompts = []
    all_sampling_params = []
    all_lora_requests = []
    job_indices = []
    
    for i, job in enumerate(jobs):
        try:
            job_input = validate_input(job["input"])
            
            # LoRA 처리
            lora_request = None
            if job_input["lora_adapter"]:
                # LoRA 어댑터 로드 로직...
                pass  # 위의 handler와 동일한 로직
            
            # 샘플링 파라미터
            sampling_params = SamplingParams(
                temperature=job_input["temperature"],
                max_tokens=job_input["max_tokens"],
                top_p=job_input["top_p"],
                top_k=job_input["top_k"],
                repetition_penalty=job_input["repetition_penalty"],
                stop=job_input["stop_sequences"],
                n=1  # 배치에서는 n=1로 고정
            )
            
            all_prompts.append(job_input["prompt"])
            all_sampling_params.append(sampling_params)
            all_lora_requests.append(lora_request)
            job_indices.append(i)
            
        except Exception as e:
            results.append({
                "status": "failed",
                "error": str(e)
            })
    
    if all_prompts:
        try:
            # 배치 생성
            outputs = llm_engine.generate(
                prompts=all_prompts,
                sampling_params=all_sampling_params[0],  # 모든 요청이 동일한 파라미터 사용
                lora_request=all_lora_requests[0] if all_lora_requests[0] else None
            )
            
            # 결과 매핑
            for i, output in enumerate(outputs):
                job_idx = job_indices[i]
                job_input = validate_input(jobs[job_idx]["input"])
                
                generated_text = output.outputs[0].text
                cleaned_text = clean_response(generated_text, job_input.get("influencer_name"))
                
                results.insert(job_idx, {
                    "status": "success",
                    "generated_text": cleaned_text,
                    "model": DEFAULT_MODEL
                })
                
        except Exception as e:
            # 배치 실패 시 모든 job 실패 처리
            error_result = {
                "status": "failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            for idx in job_indices:
                results.insert(idx, error_result)
    
    return results

def warmup_test():
    """워커 시작 시 웜업 테스트 실행"""
    logger.info("🔥 워커 웜업 테스트 시작...")
    
    warmup_success = False
    
    try:
        # test.json 파일 확인
        test_json_path = os.path.join(os.path.dirname(__file__), "test.json")
        
        if os.path.exists(test_json_path):
            logger.info(f"📄 test.json 파일 발견: {test_json_path}")
            with open(test_json_path, 'r', encoding='utf-8') as f:
                test_data = json.load(f)
                test_input = test_data.get("input", {})
                logger.info("✅ test.json 파일 로드 완료")
        else:
            logger.info("⚠️ test.json 파일이 없어 기본 테스트 입력 사용")
            test_input = {
                "user_message": "안녕하세요",
                "system_message": "당신은 도움이 되는 AI 어시스턴트입니다.",
                "influencer_name": "어시스턴트",
                "max_new_tokens": 50,
                "temperature": 0.7,
                "do_sample": True,
                "use_chat_template": True
            }
        
        # 1단계: 베이스 모델 웜업
        logger.info("🚀 1단계: 베이스 모델 웜업 중...")
        
        # vLLM 호환 입력으로 변환
        vllm_input = {
            "prompt": test_input.get("user_message", "Hello"),
            "system_message": test_input.get("system_message", DEFAULT_SYSTEM_MESSAGE),
            "influencer_name": test_input.get("influencer_name"),
            "temperature": test_input.get("temperature", 0.7),
            "max_tokens": test_input.get("max_new_tokens", 50),
            "top_p": test_input.get("top_p", 0.9),
            "top_k": test_input.get("top_k", 50),
            "repetition_penalty": test_input.get("repetition_penalty", 1.0),
            "stop_sequences": ["[|Human|", "[|System|]", "<|im_end|>", "</s>"],
            "lora_adapter": test_input.get("model_id"),
            "stream": False,
            "n": 1
        }
        
        validated_input = validate_input(vllm_input)
        
        sampling_params = SamplingParams(
            temperature=validated_input["temperature"],
            max_tokens=validated_input["max_tokens"],
            top_p=validated_input["top_p"],
            top_k=validated_input["top_k"],
            repetition_penalty=validated_input["repetition_penalty"],
            stop=validated_input["stop_sequences"],
            n=validated_input["n"]
        )
        
        # 베이스 모델 웜업 실행
        start_time = time.time()
        results = generate_text(
            prompt=validated_input["prompt"],
            sampling_params=sampling_params,
            lora_request=None
        )
        base_generation_time = time.time() - start_time
        
        if results and len(results) > 0:
            generated_text = clean_response(results[0])
            logger.info(f"✅ 베이스 모델 웜업 성공!")
            logger.info(f"📝 생성된 텍스트: '{generated_text[:100]}...'")  # 처음 100자만 표시
            logger.info(f"⏱️ 베이스 모델 생성 시간: {base_generation_time:.2f}초")
            logger.info(f"🔥 GPU가 웜업되어 첫 요청부터 빠른 응답이 가능합니다!")
            warmup_success = True
        else:
            logger.warning("⚠️ 베이스 모델 웜업 결과가 비어있습니다")
            return False
        
        # 2단계: LoRA 시스템 웜업 (어댑터가 없어도 시스템 준비)
        logger.info("🔧 2단계: LoRA 시스템 웜업 중...")
        
        # 사용 가능한 어댑터 확인
        available_adapters = []
        if os.path.exists(LORA_ADAPTERS_BASE_PATH):
            try:
                available_adapters = [d for d in os.listdir(LORA_ADAPTERS_BASE_PATH) 
                                    if os.path.isdir(os.path.join(LORA_ADAPTERS_BASE_PATH, d))]
            except:
                pass
        
        if available_adapters:
            logger.info(f"📂 사용 가능한 어댑터 발견: {available_adapters[:3]}...")  # 처음 3개만 표시
            
            # 첫 번째 어댑터로 웜업 시도
            try:
                first_adapter = available_adapters[0]
                adapter_path = os.path.join(LORA_ADAPTERS_BASE_PATH, first_adapter)
                
                logger.info(f"🔧 어댑터 웜업 시도: {first_adapter}")
                
                # 어댑터 로드 시도
                adapter_start = time.time()
                loaded_adapter = load_lora_adapter(adapter_path, first_adapter)
                adapter_load_time = time.time() - adapter_start
                
                logger.info(f"✅ 어댑터 로드 성공: {first_adapter} ({adapter_load_time:.2f}초)")
                
                # LoRA 생성 테스트
                lora_request = LoRARequest(
                    lora_name=first_adapter,
                    lora_int_id=loaded_adapter["lora_int_id"],
                    lora_path=loaded_adapter["path"]
                )
                
                lora_start = time.time()
                lora_results = generate_text(
                    prompt=validated_input["prompt"],
                    sampling_params=sampling_params,
                    lora_request=lora_request
                )
                lora_generation_time = time.time() - lora_start
                
                if lora_results and len(lora_results) > 0:
                    lora_text = clean_response(lora_results[0])
                    logger.info(f"✅ LoRA 생성 웜업 성공!")
                    logger.info(f"📝 LoRA 생성된 텍스트: '{lora_text}'")
                    logger.info(f"⏱️ LoRA 생성 시간: {lora_generation_time:.2f}초")
                else:
                    logger.warning("⚠️ LoRA 웜업 결과가 비어있습니다")
                    
            except Exception as lora_error:
                logger.warning(f"⚠️ LoRA 웜업 중 오류 (정상): {lora_error}")
                logger.info("📝 LoRA 시스템은 실제 요청 시 초기화됩니다")
        else:
            logger.info("📝 사용 가능한 LoRA 어댑터가 없음 - 베이스 모델만 준비됨")
        
        # 3단계: GPU 메모리 정리 및 상태 확인
        logger.info("🧹 3단계: GPU 메모리 최적화 중...")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            allocated = torch.cuda.memory_allocated(0) / 1e9
            reserved = torch.cuda.memory_reserved(0) / 1e9
            total = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f"📊 GPU 메모리 상태 - 할당: {allocated:.2f}GB, 예약: {reserved:.2f}GB, 총: {total:.2f}GB")
        
        logger.info("="*50)
        logger.info("🎯 vLLM 워커 웜업 완료!")
        logger.info("✅ 베이스 모델: EXAONE-3.5-2.4B-Instruct")
        logger.info("✅ GPU 메모리: 최적화 완료")
        logger.info("✅ 첫 요청부터 빠른 응답 가능")
        logger.info("="*50)
        return warmup_success
            
    except Exception as e:
        logger.error(f"❌ 웜업 테스트 실패: {e}")
        logger.error(traceback.format_exc())
        logger.warning("⚠️ 웜업 실패했지만 워커는 계속 실행됩니다")
        return False

def cleanup():
    """GPU 메모리 정리"""
    global llm_engine, loaded_adapters
    
    if llm_engine is not None:
        del llm_engine
        llm_engine = None
    
    loaded_adapters.clear()
    
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.info("🧹 GPU 메모리 정리 완료")

def stream_handler(job):
    """RunPod 폴링 기반 스트리밍 핸들러 함수"""
    try:
        logger.info("📥 새로운 폴링 기반 스트리밍 생성 요청 수신")
        
        # 스트리밍 요청 ID 생성
        stream_id = str(uuid.uuid4())
        logger.info(f"🔖 스트리밍 ID 생성: {stream_id}")
        
        # 엔진 초기화 확인
        if llm_engine is None:
            model_name = job["input"].get("model", DEFAULT_MODEL)
            initialize_engine(model_name)
        
        # 입력 검증
        job_input = validate_input(job["input"])
        job_input["stream_id"] = stream_id
        
        # 스트리밍 상태 초기화
        streaming_state = {
            "id": stream_id,
            "status": "initializing",
            "tokens": [],
            "generated_text": "",
            "token_count": 0,
            "start_time": time.time(),
            "error": None
        }
        
        # 전역 스트리밍 상태 저장소에 추가
        STREAMING_STATES[stream_id] = streaming_state
        
        # LoRA 어댑터 처리
        lora_request = None
        if job_input["lora_adapter"]:
            adapter_info = job_input["lora_adapter"]
            logger.info(f"🔧 LoRA 어댑터가 요청에 포함됨 - 필수 처리 모드")
            
            try:
                # 어댑터 정보 파싱
                if isinstance(adapter_info, dict):
                    adapter_name = adapter_info.get("name", "custom_adapter")
                    adapter_path = adapter_info.get("path", adapter_name)
                else:
                    adapter_name = str(adapter_info)
                    adapter_path = str(adapter_info)
                
                logger.info(f"🔄 LoRA 어댑터 요청 - name: '{adapter_name}', path: '{adapter_path}'")
                
                # 캐시에서 확인
                if adapter_name in loaded_adapters:
                    logger.info(f"✅ 캐시된 어댑터 사용: {adapter_name}")
                    loaded_adapter = loaded_adapters[adapter_name]
                else:
                    # 어댑터 로드 (동기 핸들러와 동일한 로직)
                    logger.info(f"🔍 어댑터 존재 여부 확인 중: {adapter_name}")
                    
                    if len(adapter_path) == 36 and adapter_path.count('-') == 4:
                        logger.info(f"🔍 UUID 형태 어댑터 ID 감지: {adapter_path}")
                        
                        possible_paths = [
                            adapter_path,
                            os.path.join(LORA_ADAPTERS_BASE_PATH, adapter_path),
                            f"hf://username/{adapter_path}",
                            f"hf://user/{adapter_name}",
                        ]
                        
                        loaded_adapter = None
                        for attempt_path in possible_paths:
                            try:
                                logger.info(f"📂 시도 중: {attempt_path}")
                                loaded_adapter = load_lora_adapter(attempt_path, adapter_name)
                                logger.info(f"✅ 어댑터 로드 성공: {attempt_path}")
                                break
                            except Exception as path_error:
                                logger.debug(f"❌ 경로 실패: {attempt_path} - {path_error}")
                                continue
                        
                        if loaded_adapter is None:
                            raise FileNotFoundError(f"모든 경로에서 어댑터를 찾을 수 없습니다: {adapter_name}")
                    else:
                        loaded_adapter = load_lora_adapter(adapter_path, adapter_name)
                
                # LoRA Request 생성
                lora_request = LoRARequest(
                    lora_name=adapter_name,
                    lora_int_id=loaded_adapter["lora_int_id"],
                    lora_path=loaded_adapter["path"]
                )
                
                logger.info(f"✅ LoRA 어댑터 준비 완료: {adapter_name}")
                
            except Exception as e:
                logger.error(f"❌ LoRA 어댑터 로드 최종 실패: {e}")
                yield {
                    "status": "failed",
                    "error": f"LoRA 어댑터를 찾을 수 없습니다: {adapter_name}",
                    "error_type": "adapter_not_found"
                }
                return
        else:
            logger.info(f"📝 베이스 모델로 스트리밍 생성 - LoRA 어댑터 없음")
        
        # 샘플링 파라미터 설정
        sampling_params = SamplingParams(
            temperature=job_input["temperature"],
            max_tokens=job_input["max_tokens"],
            top_p=job_input["top_p"],
            top_k=job_input["top_k"],
            repetition_penalty=job_input["repetition_penalty"],
            stop=job_input["stop_sequences"],
            n=1  # 스트리밍에서는 n=1 고정
        )
        
        # 백그라운드에서 텍스트 생성 시작
        logger.info("🚀 백그라운드 텍스트 생성 시작...")
        
        # 스트리밍 상태 업데이트
        streaming_state["status"] = "generating"
        streaming_state["model"] = DEFAULT_MODEL
        streaming_state["used_lora"] = job_input["lora_adapter"] is not None
        streaming_state["lora_adapter"] = adapter_name if lora_request else None
        streaming_state["temperature"] = job_input["temperature"]
        streaming_state["max_tokens"] = job_input["max_tokens"]
        
        # 백그라운드 생성 태스크 시작
        asyncio.create_task(_background_generate(
            job_input["prompt"],
            sampling_params,
            lora_request,
            stream_id,
            job_input["influencer_name"]
        ))
        
        # 즉시 스트리밍 ID 반환
        return {
            "status": "success",
            "stream_id": stream_id,
            "message": "스트리밍이 시작되었습니다. /stream/{stream_id} 엔드포인트로 상태를 확인하세요."
        }
        
        
    except Exception as e:
        error_msg = f"폴링 스트리밍 초기화 중 오류 발생: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(traceback.format_exc())
        
        return {
            "status": "failed",
            "error": error_msg,
            "traceback": traceback.format_exc()
        }

# Idle 상태 유지를 위한 백그라운드 스레드
def keep_alive_thread():
    """모델을 메모리에 유지하고 주기적으로 상태를 체크하는 스레드"""
    last_inference_time = 0
    last_status_log = 0
    
    while True:
        try:
            if llm_engine is not None:
                current_time = time.time()
                
                # GPU 메모리 상태 확인
                if torch.cuda.is_available():
                    memory_allocated = torch.cuda.memory_allocated(0) / 1e9
                    memory_reserved = torch.cuda.memory_reserved(0) / 1e9
                    memory_total = torch.cuda.get_device_properties(0).total_memory / 1e9
                    
                    # 30분마다 상태 로깅
                    if current_time - last_status_log >= 1800:
                        logger.info(f"💓 Keep-Alive - GPU 메모리: {memory_allocated:.1f}/{memory_total:.1f}GB 사용 중")
                        logger.info(f"🔥 모델이 메모리에 로드된 상태로 유지 중 - 즉시 응답 가능")
                        last_status_log = current_time
                
                # 설정된 간격마다 간단한 추론 실행하여 모델 활성 상태 유지
                if current_time - last_inference_time >= KEEP_ALIVE_INFERENCE_INTERVAL:
                    logger.info("🔄 Keep-Alive 추론 실행 중...")
                    sampling_params = SamplingParams(
                        temperature=0.1,
                        max_tokens=5,
                        top_p=0.9
                    )
                    keep_alive_prompt = create_chat_prompt(
                        user_message="Hi",
                        system_message="You are a helpful assistant."
                    )
                    _ = generate_text(keep_alive_prompt, sampling_params)
                    logger.info("✅ Keep-Alive 추론 완료 - 모델 활성 상태 확인")
                    last_inference_time = current_time
            
            # 설정된 간격마다 체크
            time.sleep(KEEP_ALIVE_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Keep-Alive 스레드 오류: {e}")
            time.sleep(60)

# RunPod 서버리스 실행
if __name__ == "__main__":
    logger.info("🚀 RunPod vLLM Generation Worker 시작")
    logger.info(f"📋 기본 모델: {DEFAULT_MODEL}")
    
    # 모델 사전 로드 설정 확인
    if PRELOAD_MODEL:
        logger.info("🔧 vLLM 엔진 사전 초기화 중...")
        logger.info(f"📋 설정: PRELOAD_MODEL={PRELOAD_MODEL}, ENABLE_KEEP_ALIVE={ENABLE_KEEP_ALIVE}")
        logger.info(f"⏱️ Keep-Alive 간격: 체크={KEEP_ALIVE_INTERVAL}초, 추론={KEEP_ALIVE_INFERENCE_INTERVAL}초")
        
        try:
            initialize_engine(DEFAULT_MODEL)
            logger.info("✅ 엔진 초기화 완료")
            
            # 웜업 테스트 실행
            warmup_success = warmup_test()
            
            if warmup_success:
                logger.info("🔥 워커 웜업 완료 - 최적의 성능으로 요청 대기 중")
            else:
                logger.warning("⚠️ 웜업 테스트 실패 - 첫 요청 시 약간의 지연이 있을 수 있습니다")
            
            # Keep-Alive 스레드 시작 (활성화된 경우)
            if ENABLE_KEEP_ALIVE:
                keep_alive = threading.Thread(target=keep_alive_thread, daemon=True)
                keep_alive.start()
                logger.info("💓 Keep-Alive 스레드 시작 - 모델이 항상 메모리에 유지됩니다")
            else:
                logger.info("💤 Keep-Alive 비활성화 - 모델이 유휴 시간 후 언로드될 수 있습니다")
                
        except Exception as e:
            logger.error(f"❌ 초기화 실패: {e}")
            logger.error(traceback.format_exc())
            logger.info("⚠️ 첫 요청 시 초기화됩니다")
    else:
        logger.info("💤 모델 사전 로드 비활성화 - 첫 요청 시 초기화됩니다")
        logger.info("💡 빠른 콜드 스타트를 위해 PRELOAD_MODEL=true 설정을 권장합니다")
    
    # 멀티 vLLM 매니저 초기화
    logger.info("🔧 멀티 vLLM 매니저 초기화 중...")
    manager = get_vllm_manager()
    logger.info(f"✅ 멀티 vLLM 매니저 준비 완료 - 최대 동시 요청: {manager.max_concurrent_requests}")
    
    # 다양한 엔드포인트 지원 (멀티 vLLM)
    runpod.serverless.start({
        "handler": handler,           # /run 엔드포인트 (멀티 vLLM)
        "sync_handler": sync_handler, # /runsync 엔드포인트 (동기)
        "stream_handler": stream_handler, # /stream 엔드포인트 (스트리밍)
        "batch_handler": batch_handler   # 배치 처리
    })