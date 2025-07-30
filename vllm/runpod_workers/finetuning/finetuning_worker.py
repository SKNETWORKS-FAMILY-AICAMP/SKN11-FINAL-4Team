"""
RunPod Serverless Worker for LoRA Fine-tuning
EXAONE 모델 파인튜닝을 RunPod에서 실행
"""
import os
import sys
import logging
import json
import torch
import traceback
from typing import Dict, Any, List, Optional
import tempfile
import shutil
from datetime import datetime

# vLLM 프로젝트의 pipeline 모듈 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
from huggingface_hub import HfApi, create_repo, Repository

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 전역 변수
DEFAULT_MODEL = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"

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
        "max_grad_norm": float(job_input.get("max_grad_norm", 0.3))
    }
    
    return validated

# 진행 상황 추적을 위한 전역 변수
current_progress = 0
current_status = ""

def update_progress(progress: int, status: str):
    """진행 상황 업데이트"""
    global current_progress, current_status
    current_progress = progress
    current_status = status
    logger.info(f"📊 진행률: {progress}% - {status}")

def handler(job):
    """RunPod 핸들러 함수"""
    try:
        logger.info("📥 새로운 파인튜닝 요청 수신")
        
        # 입력 검증
        job_input = validate_input(job["input"])
        logger.info(f"📝 QA 데이터 개수: {len(job_input['qa_data'])}")
        logger.info(f"🎯 타겟 모델: {job_input['base_model']}")
        logger.info(f"📚 학습 에폭: {job_input['training_epochs']}")
        
        # GPU 정보 출력
        if torch.cuda.is_available():
            logger.info(f"🖥️ GPU 사용: {torch.cuda.get_device_name(0)}")
            logger.info(f"📊 GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        
        # 파인튜닝 실행
        hf_url = fine_tune_model(
            qa_data=job_input["qa_data"],
            system_message=job_input["system_message"],
            hf_token=job_input["hf_token"],
            hf_repo_id=job_input["hf_repo_id"],
            base_model=job_input["base_model"],
            training_epochs=job_input["training_epochs"],
            batch_size=job_input["batch_size"],
            learning_rate=job_input["learning_rate"],
            lora_r=job_input["lora_r"],
            lora_alpha=job_input["lora_alpha"],
            lora_dropout=job_input["lora_dropout"],
            gradient_accumulation_steps=job_input["gradient_accumulation_steps"],
            warmup_steps=job_input["warmup_steps"],
            save_steps=job_input["save_steps"],
            logging_steps=job_input["logging_steps"],
            max_grad_norm=job_input["max_grad_norm"],
            progress_callback=update_progress
        )
        
        # 결과 반환
        result = {
            "status": "success",
            "hf_model_url": hf_url,
            "model_repo_id": job_input["hf_repo_id"],
            "base_model": job_input["base_model"],
            "training_epochs": job_input["training_epochs"],
            "qa_data_count": len(job_input["qa_data"]),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"✅ 파인튜닝 완료: {hf_url}")
        return result
        
    except Exception as e:
        error_msg = f"파인튜닝 처리 중 오류 발생: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(traceback.format_exc())
        
        return {
            "status": "failed",
            "error": error_msg,
            "traceback": traceback.format_exc(),
            "progress": current_progress,
            "last_status": current_status
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