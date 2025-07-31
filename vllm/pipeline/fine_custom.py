# EXAONE 3.5 2.4B LoRA 파인튜닝 예시 코드 (수정됨)

import torch
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
from huggingface_hub import HfApi
import os
import logging
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# GPU manager removed - using device_map='auto' instead

logger = logging.getLogger(__name__)
class ExaoneDataPreprocessor:
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
        
        # 채팅 템플릿 적용
        formatted_text = self.tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=False
        )
        
        return formatted_text
    
    def tokenize_function(self, examples):
        """토큰화 함수"""
        # 입력 텍스트 토큰화
        tokenized = self.tokenizer(
            examples["text"],
            truncation=True,
            padding=False,
            max_length=self.max_length,
            return_tensors=None
        )
        
        # labels을 input_ids와 동일하게 설정 (causal LM)
        tokenized["labels"] = tokenized["input_ids"].copy()
        
        return tokenized

def find_all_linear_names(model):
    """모델에서 모든 Linear 레이어 이름을 찾는 함수"""
    cls = torch.nn.Linear
    lora_module_names = set()
    for name, module in model.named_modules():
        if isinstance(module, cls):
            names = name.split('.')
            lora_module_names.add(names[-1])
    
    # 특정 모듈들은 제외 (일반적으로 LoRA에 포함하지 않음)
    if 'lm_head' in lora_module_names:
        lora_module_names.remove('lm_head')
    if 'embed_tokens' in lora_module_names:
        lora_module_names.remove('embed_tokens')
    
    return list(lora_module_names)

def load_model_and_tokenizer(model_name="LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"):
    """모델과 토크나이저 로드 - 환경 변수 기반 GPU 지정"""
    
    # 토크나이저 로드
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    # 패딩 토큰 설정 (필요한 경우)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    # GPU 설정
    finetuning_gpu_id = int(os.getenv('FINETUNING_GPU_ID', '2'))
    
    # CUDA_VISIBLE_DEVICES로 격리된 경우
    if 'CUDA_VISIBLE_DEVICES' in os.environ:
        device_map = {"": 0}  # 격리된 환경에서는 항상 device 0 사용
        logger.info(f"🔧 격리된 GPU 환경 사용 (CUDA_VISIBLE_DEVICES={os.environ['CUDA_VISIBLE_DEVICES']})")
    else:
        # 격리되지 않은 경우 특정 GPU 지정
        device_map = {"": finetuning_gpu_id}
        logger.info(f"🔧 GPU {finetuning_gpu_id} 사용")
    
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
        device_map=device_map,
        use_cache=False,  # 그래디언트 체크포인팅과 호환성을 위해
        low_cpu_mem_usage=True,  # CPU 메모리 사용량 최소화
    )
    
    # gradient checkpointing을 여기서 먼저 활성화
    model.gradient_checkpointing_enable()
    
    # 모델을 LoRA 훈련에 맞게 준비 (gradient checkpointing 후에)
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    
    return model, tokenizer

def setup_lora_config(model):
    """LoRA 설정 - 모델 구조에 맞게 자동 탐지"""
    
    # 모델에서 사용 가능한 Linear 모듈들을 자동으로 찾기
    target_modules = find_all_linear_names(model)
    print(f"발견된 Linear 모듈들: {target_modules}")
    
    # EXAONE 모델에서 일반적으로 사용되는 모듈들만 선택
    attention_modules = [name for name in target_modules if any(proj in name for proj in ['q_proj', 'k_proj', 'v_proj', 'o_proj'])]
    
    if not attention_modules:
        # attention 모듈이 없으면 다른 이름일 수 있으므로 일반적인 이름들 시도
        common_names = ['query', 'key', 'value', 'dense', 'fc1', 'fc2', 'gate_proj', 'up_proj', 'down_proj']
        attention_modules = [name for name in target_modules if any(common in name for common in common_names)]
    
    if not attention_modules:
        # 그래도 없으면 처음 몇 개만 사용
        attention_modules = target_modules[:4] if len(target_modules) >= 4 else target_modules
    
    print(f"LoRA에 사용할 모듈들: {attention_modules}")
    
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=4,  # rank를 더 줄여서 메모리 절약
        lora_alpha=8,  # alpha도 더 줄임
        lora_dropout=0.05,
        target_modules=attention_modules,
        bias="none",
        use_rslora=False,
    )
    return lora_config

def prepare_dataset(tokenizer, qa_data: list[dict], system_message: str, max_length=1024):  # max_length 줄임
    """데이터셋 준비 (예시 데이터)"""
    
    # 데이터 전처리
    preprocessor = ExaoneDataPreprocessor(tokenizer, max_length)
    
    formatted_data = []
    print(f"prepare_dataset: Received {len(qa_data)} items")
    if qa_data:
        print(f"First item sample: {qa_data[0]}")
    
    for i, item in enumerate(qa_data):
        # 이미 변환된 데이터인지 확인 (messages 키가 있는 경우)
        if "messages" in item:
            messages = item["messages"]
            
            # 멀티턴 대화인 경우 전체 대화를 하나의 텍스트로 처리
            if len(messages) > 3:  # system + 최소 1턴 이상의 대화
                # 토크나이저의 채팅 템플릿을 사용해 전체 대화를 포맷팅
                formatted_text = tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=False
                )
                formatted_data.append({"text": formatted_text})
            else:
                # 단일 턴 대화 처리 (기존 로직)
                question = ""
                answer = ""
                
                for msg in messages:
                    if msg.get("role") == "user":
                        question = msg.get("content", "")
                    elif msg.get("role") == "assistant":
                        answer = msg.get("content", "")
                
                if question and answer:
                    formatted_text = preprocessor.create_chat_format(
                        question, 
                        answer,
                        system_msg=system_message
                    )
                    formatted_data.append({"text": formatted_text})
        else:
            # 원시 QA 형식
            question = item.get("question", "")
            answer = item.get("answer", "")
            
            if not question and not answer:
                print(f"Warning: Item {i} has no question or answer: {item}")
                continue
            
            if question and answer:
                formatted_text = preprocessor.create_chat_format(
                    question, 
                    answer,
                    system_msg=system_message
                )
                formatted_data.append({"text": formatted_text})
            else:
                print(f"Warning: Item {i} incomplete - question: '{question}', answer: '{answer}'")
    
    # Dataset 객체 생성
    print(f"prepare_dataset: Successfully formatted {len(formatted_data)} items out of {len(qa_data)}")
    
    if not formatted_data:
        raise ValueError("No valid QA data found after formatting. Check data structure.")
    
    dataset = Dataset.from_list(formatted_data)
    
    # 토큰화
    tokenized_dataset = dataset.map(
        preprocessor.tokenize_function,
        batched=True,
        remove_columns=dataset.column_names
    )
    
    # 데이터 검증 및 수정
    def validate_and_fix_data(example):
        """데이터 형식 검증 및 수정"""
        # input_ids와 labels가 리스트인지 확인
        if isinstance(example['input_ids'], list) and isinstance(example['labels'], list):
            # 정상적인 경우 그대로 반환
            return example
        else:
            # 문제가 있는 경우 수정
            if not isinstance(example['input_ids'], list):
                example['input_ids'] = example['input_ids'].tolist() if hasattr(example['input_ids'], 'tolist') else [example['input_ids']]
            if not isinstance(example['labels'], list):
                example['labels'] = example['labels'].tolist() if hasattr(example['labels'], 'tolist') else [example['labels']]
            return example
    
    tokenized_dataset = tokenized_dataset.map(validate_and_fix_data)
    
    return tokenized_dataset

def setup_training_arguments(training_epochs: int, output_dir="./exaone-lora-results-system-custom"):
    """훈련 인수 설정"""
    
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,  # 줄임
        num_train_epochs=training_epochs,  
        learning_rate=2e-4,  
        lr_scheduler_type="linear",
        warmup_steps=10,  
        logging_steps=5,
        save_strategy="epoch", 
        eval_strategy="epoch", 
        load_best_model_at_end=True,
        metric_for_best_model="loss",
        greater_is_better=False,  
        bf16=True,
        gradient_checkpointing=True,  # 메모리 절약을 위해 활성화
        dataloader_pin_memory=False,
        remove_unused_columns=False,
        report_to="none",
        seed=42,
        optim="adamw_torch",
        max_grad_norm=1.0,
        dataloader_num_workers=0, 
        save_total_limit=1, 
    )
    
    return training_args

def upload_to_huggingface(output_dir, hf_token, hf_repo_id):
    """파인튜닝된 모델을 Hugging Face Hub에 업로드"""
    if not hf_token:
        print("HF_TOKEN이 설정되지 않아 업로드를 건너뜁니다.")
        return hf_repo_id  # 레포 경로만 반환
    
    try:
        print(f"\n=== Hugging Face Hub 업로드 시작 ===")
        api = HfApi()
        
        # 1. 저장소 생성
        print(f"저장소 생성 중: {hf_repo_id}")
        api.create_repo(
            repo_id=hf_repo_id,
            repo_type="model",
            private=False,
            token=hf_token,
            exist_ok=True,
        )
        
        # 2. 모델 파일 업로드
        print(f"모델 업로드 중: {output_dir} -> {hf_repo_id}")
        api.upload_folder(
            repo_id=hf_repo_id,
            folder_path=output_dir,
            repo_type="model",
            token=hf_token,
        )
        
        print(f"✅ 업로드 완료! 모델 레포: {hf_repo_id}")
        
        # 3. 로컬 폴더 삭제
        import shutil
        try:
            print(f"🗑️ 로컬 폴더 삭제 중: {output_dir}")
            shutil.rmtree(output_dir)
            print(f"✅ 로컬 폴더 삭제 완료: {output_dir}")
        except Exception as cleanup_error:
            print(f"⚠️ 로컬 폴더 삭제 실패: {cleanup_error}")
            # 삭제 실패해도 업로드는 성공했으므로 계속 진행
        
        return hf_repo_id  # 레포 경로만 반환
        
    except Exception as e:
        print(f"❌ 업로드 실패: {e}")
        return hf_repo_id  # 실패해도 레포 경로는 반환

def cleanup_gpu_memory():
    """GPU 메모리 정리 - PyTorch 직접 사용"""
    import gc
    
    # Python 가비지 컬렉션 강제 실행
    gc.collect()
    
    # PyTorch로 직접 GPU 메모리 정리
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        print("✅ GPU 메모리 캐시 정리 완료")

def main(qa_data: list[dict], system_message: str, hf_token: str, hf_repo_id: str, training_epochs: int, gpu_id:int=None) -> str:
    """메인 훈련 함수 - device_map='auto'로 자동 할당"""
    # gpu_id 파라미터는 호환성을 위해 유지하지만 사용하지 않음
    
    # 시작 전 GPU 메모리 정리
    cleanup_gpu_memory()
    
    # GPU 메모리 상태 로깅
    if torch.cuda.is_available():
        print(f"\n=== 파인튜닝 시작 시 GPU 상태 ===")
        print(f"사용 가능한 GPU 수: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            print(f"GPU {i}: {props.name}, 메모리: {props.total_memory / 1024**3:.2f}GB")
            if 'CUDA_VISIBLE_DEVICES' in os.environ:
                print(f"CUDA_VISIBLE_DEVICES: {os.environ['CUDA_VISIBLE_DEVICES']}")
    
    # 1. 모델과 토크나이저 로드
    model, tokenizer = load_model_and_tokenizer()
    
    
    # 3. LoRA 설정 및 적용
    lora_config = setup_lora_config(model)
    model = get_peft_model(model, lora_config)
    
    # PEFT 적용 후 디바이스 확인 (device_map="auto"로 이미 할당됨)
    # 7. 데이터셋 준비
    train_dataset = prepare_dataset(tokenizer, qa_data, system_message)
    print(f"훈련 데이터셋 크기: {len(train_dataset)}")
    # 데이터셋을 train/eval로 분할 (조기 종료를 위한 validation 데이터 필요)
    train_size = int(0.8 * len(train_dataset))
    eval_size = len(train_dataset) - train_size
    
    train_dataset_split = train_dataset.select(range(train_size))
    eval_dataset = train_dataset.select(range(train_size, train_size + eval_size))
    
    print(f"훈련 데이터: {len(train_dataset_split)}, 검증 데이터: {len(eval_dataset)}")
    
    # 8. 데이터 콜레이터 설정 - 더 안전한 방식
    
    def data_collator(features):
        """커스텀 데이터 콜레이터"""
        # 입력 길이 확인
        max_length = max(len(f["input_ids"]) for f in features)
        
        batch = {
            "input_ids": [],
            "attention_mask": [],
            "labels": []
        }
        
        for feature in features:
            input_ids = feature["input_ids"]
            labels = feature["labels"]
            
            # 패딩 추가
            padding_length = max_length - len(input_ids)
            
            # input_ids 패딩
            padded_input_ids = input_ids + [tokenizer.pad_token_id] * padding_length
            
            # attention_mask 생성
            attention_mask = [1] * len(input_ids) + [0] * padding_length
            
            # labels 패딩 (-100은 loss 계산에서 무시됨)
            padded_labels = labels + [-100] * padding_length
            
            batch["input_ids"].append(padded_input_ids)
            batch["attention_mask"].append(attention_mask)
            batch["labels"].append(padded_labels)
        
        # 텐서 생성 (Trainer가 자동으로 올바른 디바이스로 이동시킴)
        return {
            "input_ids": torch.tensor(batch["input_ids"], dtype=torch.long),
            "attention_mask": torch.tensor(batch["attention_mask"], dtype=torch.long),
            "labels": torch.tensor(batch["labels"], dtype=torch.long)
        }
    print("여기는 오고 안되는거야? ")
    # 9. 훈련 인수 설정
    training_args = setup_training_arguments(training_epochs)
    
    # 10. 조기 종료 콜백 설정
    early_stopping_callback = EarlyStoppingCallback(
        early_stopping_patience=2,  # 2 epoch 동안 개선이 없으면 종료
        early_stopping_threshold=0.01  # 최소 개선 임계값
    )
    # 11. Trainer 초기화
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset_split,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
        callbacks=[early_stopping_callback]
    )
    
    try:
        # GPU 메모리 상태 확인
        if torch.cuda.is_available():
            gpu_memory_before = torch.cuda.memory_allocated() / 1024**3
            print(f"🔍 훈련 시작 전 GPU 메모리 사용량: {gpu_memory_before:.2f}GB")
        
        trainer.train()
        print("훈련 완료!")
    except RuntimeError as e:
        if "out of memory" in str(e) or "CUDA out of memory" in str(e):
            print(f"❌ GPU 메모리 부족 오류 발생: {e}")
            
            # GPU 메모리 상태 출력
            if torch.cuda.is_available():
                print(f"\n=== GPU 메모리 상태 ===")
                print(f"할당된 메모리: {torch.cuda.memory_allocated() / 1024**3:.2f}GB")
                print(f"예약된 메모리: {torch.cuda.memory_reserved() / 1024**3:.2f}GB")
                print(f"최대 할당 메모리: {torch.cuda.max_memory_allocated() / 1024**3:.2f}GB")
                
                # 메모리 정리 시도
                torch.cuda.empty_cache()
                print("GPU 메모리 캐시 정리 완료")
            
            # 더 작은 설정으로 재시도 제안
            print("\n💡 해결 방법:")
            print("1. batch_size를 줄이거나 gradient_accumulation_steps를 늘리세요")
            print("2. max_length를 줄이세요 (현재 1024)")
            print("3. LoRA rank를 줄이세요 (현재 8)")
            print("4. 더 큰 GPU를 사용하세요")
            
            raise
        else:
            print(f"훈련 중 오류 발생: {e}")
            
            # 더 자세한 디버깅 정보
            print("\n=== 추가 디버깅 정보 ===")
            print(f"모델 타입: {type(model)}")
            print(f"Base model 타입: {type(model.base_model) if hasattr(model, 'base_model') else 'N/A'}")
            
            # PEFT 설정 확인
            if hasattr(model, 'peft_config'):
                print(f"PEFT config: {model.peft_config}")
            
            # GPU 메모리 상태
            if torch.cuda.is_available():
                print(f"\n=== GPU 메모리 상태 ===")
                print(f"할당된 메모리: {torch.cuda.memory_allocated() / 1024**3:.2f}GB")
                print(f"예약된 메모리: {torch.cuda.memory_reserved() / 1024**3:.2f}GB")
            
            raise
    
    # 14. 모델 저장
    trainer.save_model()
    print(f"모델이 {training_args.output_dir}에 저장되었습니다.")
    
    # 15. Hugging Face Hub에 업로드
    hf_model_url = upload_to_huggingface(training_args.output_dir, hf_token, hf_repo_id)
    
    # 16. 모델과 트레이너 메모리 해제
    print("🧹 메모리 정리 중...")
    try:
        # 모델을 CPU로 이동 후 삭제
        if hasattr(model, 'cpu'):
            model.cpu()
        del model
        del trainer
        del tokenizer
        if 'train_dataset' in locals():
            del train_dataset
        if 'train_dataset_split' in locals():
            del train_dataset_split
        if 'eval_dataset' in locals():
            del eval_dataset
        
        # GPU 메모리 정리
        cleanup_gpu_memory()
        
        print("✅ 메모리 정리 완료")
    except Exception as e:
        print(f"⚠️ 메모리 정리 중 오류 (무시됨): {e}")
    
    # 17. HuggingFace 모델 레포 경로 반환
    print(f"✅ 파인튜닝 완료! 모델 레포: {hf_model_url}")
    return hf_model_url