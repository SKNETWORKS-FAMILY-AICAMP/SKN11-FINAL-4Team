"""
RunPod Serverless Worker for LoRA Fine-tuning
EXAONE 모델 파인튜닝을 RunPod에서 실행
"""
import os
import logging
import torch
import traceback
from typing import Dict, Any, List
import tempfile
from datetime import datetime
import requests
import json
import threading
import time
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
load_dotenv()

import runpod
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer, 
    TrainingArguments, 
    Trainer,
    DataCollatorForLanguageModeling,
    EarlyStoppingCallback
)
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from datasets import Dataset
from huggingface_hub import HfApi, create_repo

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 전역 변수
DEFAULT_MODEL = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
BACKEND_POST_URL = os.getenv('BACKEND_POST_URL', 'http://localhost:8000/api/v1/influencers/finetuning/result')

class ExaoneDataPreprocessor:
    """EXAONE 모델용 데이터 전처리"""
    def __init__(self, tokenizer, max_length=2048):
        self.tokenizer = tokenizer
        self.max_length = max_length
        
    def create_chat_format(self, instruction, output, system_msg: str):
        """EXAONE 채팅 형식으로 데이터 변환"""
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": instruction},
            {"role": "assistant", "content": output}
        ]
        
        formatted_text = self.tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=False
        )
        
        return formatted_text
    
    def tokenize_function(self, examples):
        """토큰화 함수"""
        tokenized = self.tokenizer(
            examples["text"],
            truncation=True,
            padding=False,
            max_length=self.max_length,
            return_tensors=None
        )
        
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

def find_all_linear_names(model):
    """모델에서 모든 Linear 레이어 이름 찾기"""
    cls = torch.nn.Linear
    lora_module_names = set()
    for name, module in model.named_modules():
        if isinstance(module, cls):
            names = name.split('.')
            lora_module_names.add(names[-1])
    
    # 특정 모듈 제외
    if 'lm_head' in lora_module_names:
        lora_module_names.remove('lm_head')
    if 'embed_tokens' in lora_module_names:
        lora_module_names.remove('embed_tokens')
    
    return list(lora_module_names)

def prepare_dataset(qa_data: List[Dict], system_message: str, tokenizer, max_length: int = 2048):
    """데이터셋 준비"""
    preprocessor = ExaoneDataPreprocessor(tokenizer, max_length)
    
    # 데이터 변환
    formatted_data = []
    for item in qa_data:
        text = preprocessor.create_chat_format(
            instruction=item['question'],
            output=item['answer'],
            system_msg=system_message
        )
        formatted_data.append({"text": text})
    
    # Dataset 생성
    dataset = Dataset.from_list(formatted_data)
    
    # 토큰화
    tokenized_dataset = dataset.map(
        preprocessor.tokenize_function,
        batched=True,
        remove_columns=dataset.column_names
    )
    
    return tokenized_dataset

def send_to_backend_sync(result_data: Dict[str, Any]):
    """파인튜닝 결과를 Backend로 전송 (동기 방식)"""
    backend_url = BACKEND_POST_URL
    
    if not backend_url:
        logger.warning("BACKEND_POST_URL이 설정되지 않음")
        return None
    
    try:
        logger.info(f"📤 Backend로 파인튜닝 결과 전송: {backend_url}")
        logger.info(f"📦 페이로드 크기: {len(json.dumps(result_data))} bytes")
        
        response = requests.post(
            backend_url,
            json=result_data,
            timeout=60  # 파인튜닝 결과는 큰 데이터일 수 있으므로 타임아웃 증가
        )
        
        if response.status_code == 200:
            logger.info(f"✅ 백엔드로 결과 전송 성공: {result_data['task_id']}")
            return response.json()
        else:
            logger.error(f"❌ 백엔드 응답 오류: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ 백엔드 전송 실패: {e}")
        return None

def upload_to_huggingface(output_dir: str, hf_token: str, hf_repo_id: str) -> str:
    """Hugging Face에 모델 업로드"""
    try:
        api = HfApi()
        
        # 리포지토리 생성 또는 확인
        try:
            create_repo(
                repo_id=hf_repo_id,
                token=hf_token,
                private=True,
                exist_ok=True
            )
        except Exception as e:
            logger.warning(f"리포지토리 생성 중 경고: {e}")
        
        # 모든 파일 업로드
        api.upload_folder(
            folder_path=output_dir,
            repo_id=hf_repo_id,
            token=hf_token,
            commit_message="LoRA fine-tuning via RunPod"
        )
        
        # URL 반환
        hf_url = f"https://huggingface.co/{hf_repo_id}"
        logger.info(f"✅ 모델 업로드 완료: {hf_url}")
        return hf_url
        
    except Exception as e:
        logger.error(f"Hugging Face 업로드 실패: {e}")
        raise

def fine_tune_model(
    qa_data: List[Dict],
    system_message: str,
    hf_token: str,
    hf_repo_id: str,
    base_model: str = DEFAULT_MODEL,
    training_epochs: int = 3,
    batch_size: int = 1,
    learning_rate: float = 3e-4,
    lora_r: int = 32,
    lora_alpha: int = 64,
    lora_dropout: float = 0.0,
    gradient_accumulation_steps: int = 8,
    warmup_steps: int = 10,
    save_steps: int = 50,
    logging_steps: int = 10,
    max_grad_norm: float = 0.3,
    progress_callback=None
) -> str:
    """파인튜닝 실행"""
    
    logger.info(f"🔧 파인튜닝 시작: {base_model}")
    
    # 임시 디렉토리 생성
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = os.path.join(temp_dir, "finetuned_model")
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. 모델과 토크나이저 로드
        logger.info("📥 모델 로드 중...")
        if progress_callback:
            progress_callback(10, "모델 로드 중...")
        
        tokenizer = AutoTokenizer.from_pretrained(base_model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            tokenizer.pad_token_id = tokenizer.eos_token_id
        
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True
        )
        
        # 2. LoRA 설정
        logger.info("🔧 LoRA 설정 중...")
        if progress_callback:
            progress_callback(20, "LoRA 설정 중...")
        
        target_modules = find_all_linear_names(model)
        
        lora_config = LoraConfig(
            r=lora_r,
            lora_alpha=lora_alpha,
            target_modules=target_modules,
            lora_dropout=lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        
        model = prepare_model_for_kbit_training(model)
        model = get_peft_model(model, lora_config)
        
        # 3. 데이터셋 준비
        logger.info("📊 데이터셋 준비 중...")
        if progress_callback:
            progress_callback(30, "데이터셋 준비 중...")
        
        tokenized_dataset = prepare_dataset(qa_data, system_message, tokenizer)
        
        # 데이터셋을 train/validation으로 분할 (90:10 비율)
        train_test_split = tokenized_dataset.train_test_split(test_size=0.1, seed=42)
        train_dataset = train_test_split['train']
        eval_dataset = train_test_split['test']
        
        logger.info(f"📊 Train 데이터: {len(train_dataset)}개, Validation 데이터: {len(eval_dataset)}개")
        
        # 4. 트레이닝 설정
        # TrainingArguments 파라미터 준비
        training_kwargs = {
            "output_dir": output_dir,
            "num_train_epochs": training_epochs,
            "per_device_train_batch_size": batch_size,
            "gradient_accumulation_steps": gradient_accumulation_steps,
            "warmup_steps": warmup_steps,
            "save_steps": save_steps,
            "logging_steps": logging_steps,
            "learning_rate": learning_rate,
            "weight_decay": 0.001,
            "fp16": False,
            "bf16": True,
            "max_grad_norm": max_grad_norm,
            "save_total_limit": 3,
            "load_best_model_at_end": True,
            "metric_for_best_model": "loss",
            "greater_is_better": False,
            "eval_steps": save_steps,
            "per_device_eval_batch_size": batch_size,
            "group_by_length": True,
            "report_to": ["none"],
            "remove_unused_columns": False,
        }
        
        # evaluation_strategy vs eval_strategy 호환성 처리
        try:
            # 최신 버전 시도
            training_kwargs["evaluation_strategy"] = "steps"
            training_args = TrainingArguments(**training_kwargs)
        except TypeError:
            # 구버전 호환성
            training_kwargs.pop("evaluation_strategy", None)
            training_kwargs["eval_strategy"] = "steps"
            training_args = TrainingArguments(**training_kwargs)
        
        # 5. 트레이너 설정
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=tokenizer,
            mlm=False,
        )
        
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,  # train_dataset으로 변경
            eval_dataset=eval_dataset,     # eval_dataset 추가
            tokenizer=tokenizer,
            data_collator=data_collator,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]  # EarlyStoppingCallback 복원
        )
        
        # 6. 학습 실행
        logger.info("🚀 학습 시작...")
        if progress_callback:
            progress_callback(40, "학습 시작...")
        
        trainer.train()
        
        # 7. 모델 저장
        logger.info("💾 모델 저장 중...")
        if progress_callback:
            progress_callback(80, "모델 저장 중...")
        
        trainer.save_model()
        tokenizer.save_pretrained(output_dir)
        
        # 8. Hugging Face 업로드
        logger.info("📤 Hugging Face 업로드 중...")
        if progress_callback:
            progress_callback(90, "Hugging Face 업로드 중...")
        
        hf_url = upload_to_huggingface(output_dir, hf_token, hf_repo_id)
        
        if progress_callback:
            progress_callback(100, "파인튜닝 완료!")
        
        return hf_url

def validate_input(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """입력 데이터 검증"""
    # 필수 필드 확인
    required_fields = ["qa_data", "system_message", "hf_token", "hf_repo_id"]
    for field in required_fields:
        if field not in job_input:
            raise ValueError(f"{field} 필드는 필수입니다.")
    
    # QA 데이터 검증
    qa_data = job_input["qa_data"]
    if not isinstance(qa_data, list) or len(qa_data) == 0:
        raise ValueError("qa_data는 비어있지 않은 리스트여야 합니다.")
    
    for item in qa_data:
        if not isinstance(item, dict) or "question" not in item or "answer" not in item:
            raise ValueError("각 QA 항목은 'question'과 'answer' 필드를 포함해야 합니다.")
    
    # 검증된 입력 반환
    validated = {
        "qa_data": qa_data,
        "system_message": job_input["system_message"],
        "hf_token": job_input["hf_token"],
        "hf_repo_id": job_input["hf_repo_id"],
        "base_model": job_input.get("base_model", DEFAULT_MODEL),
        "training_epochs": int(job_input.get("training_epochs", 3)),
        "batch_size": int(job_input.get("batch_size", 1)),
        "learning_rate": float(job_input.get("learning_rate", 3e-4)),
        "lora_r": int(job_input.get("lora_r", 32)),
        "lora_alpha": int(job_input.get("lora_alpha", 64)),
        "lora_dropout": float(job_input.get("lora_dropout", 0.0)),
        "gradient_accumulation_steps": int(job_input.get("gradient_accumulation_steps", 8)),
        "warmup_steps": int(job_input.get("warmup_steps", 10)),
        "save_steps": int(job_input.get("save_steps", 50)),
        "logging_steps": int(job_input.get("logging_steps", 10)),
        "max_grad_norm": float(job_input.get("max_grad_norm", 0.3)),
        "task_id": job_input.get("task_id", "unknown"),
        "influencer_id": job_input.get("influencer_id", "")
    }
    
    return validated

class MultiFineTuningManager:
    """멀티 파인튜닝 관리자"""
    
    def __init__(self, max_concurrent_jobs=2, vram_threshold=0.75):
        self.max_concurrent_jobs = max_concurrent_jobs
        self.vram_threshold = vram_threshold
        self.job_queue = Queue()
        self.active_jobs = {}
        self.job_results = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_jobs)
        self.running = True
        
        # 스케줄러 스레드 시작
        self.scheduler_thread = threading.Thread(target=self._job_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info(f"🔧 멀티 파인튜닝 매니저 초기화 - 최대 동시 작업: {max_concurrent_jobs}, VRAM 임계값: {vram_threshold}")
    
    def get_vram_usage(self):
        """현재 VRAM 사용량 확인"""
        if torch.cuda.is_available():
            allocated_memory = torch.cuda.memory_allocated(0)
            total_memory = torch.cuda.get_device_properties(0).total_memory
            usage = allocated_memory / total_memory
            logger.debug(f"📊 VRAM 사용량: {usage:.2%} ({allocated_memory/1e9:.2f}GB / {total_memory/1e9:.2f}GB)")
            return usage
        return 0
    
    def get_available_vram_gb(self):
        """사용 가능한 VRAM (GB) 계산"""
        if torch.cuda.is_available():
            total_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            allocated_memory = torch.cuda.memory_allocated(0) / 1e9
            available = total_memory - allocated_memory
            return available
        return 0
    
    def calculate_max_jobs_by_vram(self):
        """VRAM 기반으로 최대 동시 작업 수 동적 계산"""
        total_vram = torch.cuda.get_device_properties(0).total_memory / 1e9 if torch.cuda.is_available() else 0
        current_usage = self.get_vram_usage()
        available_ratio = 1 - current_usage
        
        # VRAM 기반 동시 작업 수 계산
        if total_vram >= 80:  # H100 80GB
            base_jobs = 6
        elif total_vram >= 40:  # A100 40GB
            base_jobs = 4
        elif total_vram >= 24:  # RTX 4090, A6000 24GB
            base_jobs = 2
        else:  # < 24GB
            base_jobs = 1
        
        # 현재 사용량에 따라 조정
        if available_ratio < 0.3:  # 사용량이 70% 이상
            max_jobs = max(1, base_jobs - 2)
        elif available_ratio < 0.5:  # 사용량이 50% 이상
            max_jobs = max(1, base_jobs - 1)
        else:
            max_jobs = base_jobs
        
        return min(max_jobs, self.max_concurrent_jobs)
    
    def can_start_new_job(self):
        """새 작업을 시작할 수 있는지 확인"""
        current_jobs = len(self.active_jobs)
        vram_usage = self.get_vram_usage()
        max_jobs = self.calculate_max_jobs_by_vram()
        
        can_start = (current_jobs < max_jobs and vram_usage < self.vram_threshold)
        
        if not can_start:
            logger.debug(f"📊 작업 시작 불가 - 현재 작업: {current_jobs}/{max_jobs}, VRAM: {vram_usage:.1%}")
        
        return can_start
    
    def add_job(self, job_data):
        """작업을 큐에 추가"""
        job_id = job_data.get('job_id', f"job_{int(time.time())}")
        job_data['job_id'] = job_id
        
        self.job_queue.put(job_data)
        logger.info(f"📥 작업 추가됨 - ID: {job_id}, 큐 크기: {self.job_queue.qsize()}")
        
        return job_id
    
    def get_job_result(self, job_id, timeout=3600):  # 1시간 타임아웃
        """작업 결과 조회 (블로킹)"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.lock:
                if job_id in self.job_results:
                    result = self.job_results.pop(job_id)
                    logger.info(f"✅ 작업 결과 반환 - ID: {job_id}")
                    return result
            
            time.sleep(1)  # 1초마다 체크
        
        logger.error(f"⏰ 작업 타임아웃 - ID: {job_id}")
        return {"status": "timeout", "error": "작업이 시간 초과되었습니다."}
    
    def _execute_finetuning_job(self, job_data):
        """개별 파인튜닝 작업 실행"""
        job_id = job_data['job_id']
        
        try:
            logger.info(f"🚀 파인튜닝 시작 - ID: {job_id}")
            
            # GPU 메모리 정리
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # 파인튜닝 실행
            hf_url = fine_tune_model(
                qa_data=job_data["qa_data"],
                system_message=job_data["system_message"],
                hf_token=job_data["hf_token"],
                hf_repo_id=job_data["hf_repo_id"],
                base_model=job_data.get("base_model", DEFAULT_MODEL),
                training_epochs=job_data.get("training_epochs", 3),
                batch_size=job_data.get("batch_size", 1),
                learning_rate=job_data.get("learning_rate", 3e-4),
                lora_r=job_data.get("lora_r", 32),
                lora_alpha=job_data.get("lora_alpha", 64),
                lora_dropout=job_data.get("lora_dropout", 0.0),
                gradient_accumulation_steps=job_data.get("gradient_accumulation_steps", 8),
                warmup_steps=job_data.get("warmup_steps", 10),
                save_steps=job_data.get("save_steps", 50),
                logging_steps=job_data.get("logging_steps", 10),
                max_grad_norm=job_data.get("max_grad_norm", 0.3),
                progress_callback=lambda p, s: logger.info(f"📊 [{job_id}] {p}% - {s}")
            )
            
            # 성공 결과
            result = {
                "status": "success",
                "job_id": job_id,
                "hf_model_url": hf_url,
                "model_repo_id": job_data["hf_repo_id"],
                "base_model": job_data.get("base_model", DEFAULT_MODEL),
                "training_epochs": job_data.get("training_epochs", 3),
                "qa_data_count": len(job_data["qa_data"]),
                "timestamp": datetime.now().isoformat()
            }
            
            # 백엔드로 결과 전송
            backend_data = {
                "task_id": job_data.get("task_id", job_id),
                "influencer_id": job_data.get("influencer_id", ""),
                "status": "completed",
                "hf_model_url": hf_url,
                "error_message": None,
                "metadata": {
                    "training_epochs": job_data.get("training_epochs", 3),
                    "qa_data_count": len(job_data["qa_data"]),
                    "hf_repo_id": job_data["hf_repo_id"],
                    "base_model": job_data.get("base_model", DEFAULT_MODEL)
                }
            }
            
            backend_response = send_to_backend_sync(backend_data)
            if backend_response:
                logger.info(f"✅ [{job_id}] Backend 응답: {backend_response}")
            
            logger.info(f"✅ 파인튜닝 완료 - ID: {job_id}")
            return result
            
        except Exception as e:
            error_msg = f"파인튜닝 실행 중 오류: {str(e)}"
            logger.error(f"❌ [{job_id}] {error_msg}")
            logger.error(traceback.format_exc())
            
            # 실패 결과
            result = {
                "status": "failed",
                "job_id": job_id,
                "error": error_msg,
                "traceback": traceback.format_exc()
            }
            
            # 백엔드로 실패 결과 전송
            backend_data = {
                "task_id": job_data.get("task_id", job_id),
                "influencer_id": job_data.get("influencer_id", ""),
                "status": "failed",
                "hf_model_url": None,
                "error_message": error_msg,
                "metadata": {
                    "training_epochs": job_data.get("training_epochs", 3),
                    "qa_data_count": len(job_data.get("qa_data", [])),
                    "hf_repo_id": job_data.get("hf_repo_id", "")
                }
            }
            
            backend_response = send_to_backend_sync(backend_data)
            if backend_response:
                logger.info(f"✅ [{job_id}] Backend 응답: {backend_response}")
            
            return result
        
        finally:
            # GPU 메모리 정리
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    
    def _job_scheduler(self):
        """작업 스케줄러 - 백그라운드에서 실행"""
        logger.info("🔄 작업 스케줄러 시작")
        
        while self.running:
            try:
                # 새 작업 시작 가능한지 확인
                if self.can_start_new_job() and not self.job_queue.empty():
                    try:
                        job_data = self.job_queue.get_nowait()
                        job_id = job_data['job_id']
                        
                        # 작업 시작
                        future = self.executor.submit(self._execute_finetuning_job, job_data)
                        
                        with self.lock:
                            self.active_jobs[job_id] = future
                        
                        logger.info(f"🚀 작업 시작 - ID: {job_id}, 활성 작업: {len(self.active_jobs)}")
                        
                        # 완료된 작업 확인 및 정리
                        self._cleanup_completed_jobs()
                        
                    except Empty:
                        pass
                
                # 완료된 작업 정리
                self._cleanup_completed_jobs()
                
                # VRAM 상태 로깅 (10초마다)
                if int(time.time()) % 10 == 0:
                    vram_usage = self.get_vram_usage()
                    available_vram = self.get_available_vram_gb()
                    max_jobs = self.calculate_max_jobs_by_vram()
                    logger.info(f"📊 시스템 상태 - VRAM: {vram_usage:.1%}, 사용가능: {available_vram:.1f}GB, 최대작업: {max_jobs}, 활성작업: {len(self.active_jobs)}, 대기작업: {self.job_queue.qsize()}")
                
                time.sleep(2)  # 2초마다 체크
                
            except Exception as e:
                logger.error(f"❌ 스케줄러 오류: {e}")
                time.sleep(5)
    
    def _cleanup_completed_jobs(self):
        """완료된 작업 정리"""
        completed_jobs = []
        
        with self.lock:
            for job_id, future in list(self.active_jobs.items()):
                if future.done():
                    try:
                        result = future.result()
                        self.job_results[job_id] = result
                        completed_jobs.append(job_id)
                        logger.info(f"✅ 작업 완료 - ID: {job_id}, 상태: {result.get('status', 'unknown')}")
                    except Exception as e:
                        error_result = {
                            "status": "failed",
                            "job_id": job_id,
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        }
                        self.job_results[job_id] = error_result
                        completed_jobs.append(job_id)
                        logger.error(f"❌ 작업 실행 중 오류 - ID: {job_id}, 오류: {e}")
            
            # 완료된 작업 제거
            for job_id in completed_jobs:
                self.active_jobs.pop(job_id, None)
    
    def shutdown(self):
        """매니저 종료"""
        logger.info("🛑 멀티 파인튜닝 매니저 종료 중...")
        self.running = False
        self.executor.shutdown(wait=True)

# 전역 매니저 인스턴스
manager = None

def get_manager():
    """매니저 인스턴스 반환 (싱글톤)"""
    global manager
    if manager is None:
        # GPU 메모리에 따라 최대 동시 작업 수 결정
        if torch.cuda.is_available():
            total_vram = torch.cuda.get_device_properties(0).total_memory / 1e9
            if total_vram >= 80:  # H100
                max_jobs = 6
            elif total_vram >= 40:  # A100
                max_jobs = 4
            elif total_vram >= 24:  # RTX 4090
                max_jobs = 2
            else:
                max_jobs = 1
        else:
            max_jobs = 1
        
        manager = MultiFineTuningManager(max_concurrent_jobs=max_jobs, vram_threshold=0.75)
        logger.info(f"🔧 매니저 생성됨 - 최대 동시 작업: {max_jobs}")
    
    return manager

# 진행 상황 추적을 위한 전역 변수 (하위 호환성)
current_progress = 0
current_status = ""

def update_progress(progress: int, status: str):
    """진행 상황 업데이트 (하위 호환성)"""
    global current_progress, current_status
    current_progress = progress
    current_status = status
    logger.info(f"📊 진행률: {progress}% - {status}")

def handler(job):
    """RunPod 핸들러 함수 - 멀티 파인튜닝 지원"""
    try:
        logger.info("📥 새로운 파인튜닝 요청 수신")
        
        # RunPod job ID 추출
        runpod_job_id = job.get("id", "unknown")
        
        # 입력 검증
        job_input = validate_input(job["input"])
        logger.info(f"📝 QA 데이터 개수: {len(job_input['qa_data'])}")
        logger.info(f"🎯 타겟 모델: {job_input['base_model']}")
        logger.info(f"📚 학습 에폭: {job_input['training_epochs']}")
        
        # GPU 정보 출력
        if torch.cuda.is_available():
            logger.info(f"🖥️ GPU 사용: {torch.cuda.get_device_name(0)}")
            logger.info(f"📊 GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        
        # 멀티 파인튜닝 매니저 가져오기
        multi_manager = get_manager()
        
        # 작업 데이터 준비
        job_data = {
            "runpod_job_id": runpod_job_id,
            "task_id": job_input["task_id"],
            "influencer_id": job_input["influencer_id"],
            "qa_data": job_input["qa_data"],
            "system_message": job_input["system_message"],
            "hf_token": job_input["hf_token"],
            "hf_repo_id": job_input["hf_repo_id"],
            "base_model": job_input["base_model"],
            "training_epochs": job_input["training_epochs"],
            "batch_size": job_input["batch_size"],
            "learning_rate": job_input["learning_rate"],
            "lora_r": job_input["lora_r"],
            "lora_alpha": job_input["lora_alpha"],
            "lora_dropout": job_input["lora_dropout"],
            "gradient_accumulation_steps": job_input["gradient_accumulation_steps"],
            "warmup_steps": job_input["warmup_steps"],
            "save_steps": job_input["save_steps"],
            "logging_steps": job_input["logging_steps"],
            "max_grad_norm": job_input["max_grad_norm"]
        }
        
        # 현재 시스템 상태 로깅
        vram_usage = multi_manager.get_vram_usage()
        available_vram = multi_manager.get_available_vram_gb()
        max_jobs = multi_manager.calculate_max_jobs_by_vram()
        active_jobs = len(multi_manager.active_jobs)
        queue_size = multi_manager.job_queue.qsize()
        
        logger.info(f"📊 시스템 상태 - VRAM: {vram_usage:.1%}, 사용가능: {available_vram:.1f}GB, 최대작업: {max_jobs}, 활성작업: {active_jobs}, 대기작업: {queue_size}")
        
        # 작업을 큐에 추가
        job_id = multi_manager.add_job(job_data)
        logger.info(f"📥 작업 큐에 추가됨 - Job ID: {job_id}")
        
        # 작업 결과 대기 (블로킹)
        logger.info(f"⏳ 작업 완료 대기 중 - Job ID: {job_id}")
        result = multi_manager.get_job_result(job_id, timeout=7200)  # 2시간 타임아웃
        
        # 결과 처리
        if result["status"] == "success":
            logger.info(f"✅ 파인튜닝 완료 - Job ID: {job_id}, HF URL: {result.get('hf_model_url', 'N/A')}")
            return result
        elif result["status"] == "timeout":
            logger.error(f"⏰ 파인튜닝 타임아웃 - Job ID: {job_id}")
            return {
                "status": "failed",
                "error": "파인튜닝 작업이 시간 초과되었습니다.",
                "job_id": job_id,
                "timeout": True
            }
        else:
            logger.error(f"❌ 파인튜닝 실패 - Job ID: {job_id}, 오류: {result.get('error', 'Unknown error')}")
            return result
        
    except Exception as e:
        error_msg = f"파인튜닝 핸들러 오류: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(traceback.format_exc())
        
        # 실패 결과 백엔드로 전송
        try:
            job_input = validate_input(job["input"])
            result_data = {
                "task_id": job_input.get("task_id", "unknown"),
                "influencer_id": job_input.get("influencer_id", ""),
                "status": "failed",
                "hf_model_url": None,
                "error_message": str(e),
                "metadata": {
                    "training_epochs": job_input.get("training_epochs", 3),
                    "qa_data_count": len(job_input.get("qa_data", [])),
                    "hf_repo_id": job_input.get("hf_repo_id", "")
                }
            }
            
            backend_response = send_to_backend_sync(result_data)
            if backend_response:
                logger.info(f"✅ Backend 응답: {backend_response}")
        except:
            logger.error("백엔드 전송 중 추가 오류 발생")
        
        return {
            "status": "failed",
            "error": error_msg,
            "traceback": traceback.format_exc()
        }

# GPU 메모리 정리 함수
def cleanup():
    """GPU 메모리 정리"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.info("🧹 GPU 메모리 정리 완료")

# RunPod 서버리스 실행
if __name__ == "__main__":
    logger.info("🚀 RunPod Fine-tuning Worker 시작")
    runpod.serverless.start({"handler": handler})