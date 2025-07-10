# EXAONE 3.5 2.4B LoRA 파인튜닝 예시 코드 (수정됨)

import torch
import json
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

logger = logging.getLogger(__name__)

# GPU 설정 확인
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Hugging Face 토큰 및 repo_id 설정 (환경 변수에서 가져오기)


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
    """모델과 토크나이저 로드"""
    print("모델과 토크나이저 로딩 중...")
    
    # GPU 할당 확인
    from pipeline.gpu_utils import find_available_gpu, log_gpu_status
    
    # 현재 GPU 상태 로깅
    log_gpu_status()
    
    # 사용 가능한 GPU 찾기
    available_gpu = find_available_gpu(min_memory_mb=10240)  # 10GB 이상 여유 메모리
    
    if available_gpu is not None:
        # 특정 GPU만 사용하도록 설정
        os.environ['CUDA_VISIBLE_DEVICES'] = str(available_gpu)
        print(f"파인튜닝에 GPU {available_gpu} 사용")
        device_map = "auto"  # 단일 GPU에서 auto는 전체 모델을 해당 GPU에 로드
    else:
        # 사용 가능한 GPU가 없으면 기본 동작
        print("경고: 여유 있는 GPU를 찾을 수 없습니다. 기본 설정 사용")
        device_map = "auto"
    
    # 토크나이저 로드
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    # 패딩 토큰 설정 (필요한 경우)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    # 모델 로드 - gradient checkpointing 문제 해결을 위한 수정된 설정
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
        device_map=device_map,
        use_cache=False,  # 그래디언트 체크포인팅과 호환성을 위해
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
        r=8,  # rank를 줄여서 안정성 확보
        lora_alpha=16,  # alpha도 줄임
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
            # 이미 변환된 형식에서 question/answer 추출
            messages = item["messages"]
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
        gradient_checkpointing=False, 
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
        return f"https://huggingface.co/{hf_repo_id}"  # 토큰이 없어도 URL은 반환
    
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
        
        print(f"✅ 업로드 완료! 모델 URL: https://huggingface.co/{hf_repo_id}")
        
        # 3. 로컬 폴더 삭제
        import shutil
        try:
            print(f"🗑️ 로컬 폴더 삭제 중: {output_dir}")
            shutil.rmtree(output_dir)
            print(f"✅ 로컬 폴더 삭제 완료: {output_dir}")
        except Exception as cleanup_error:
            print(f"⚠️ 로컬 폴더 삭제 실패: {cleanup_error}")
            # 삭제 실패해도 업로드는 성공했으므로 계속 진행
        
        return f"https://huggingface.co/{hf_repo_id}"
        
    except Exception as e:
        print(f"❌ 업로드 실패: {e}")
        return f"https://huggingface.co/{hf_repo_id}"  # 실패해도 URL은 반환

def cleanup_gpu_memory():
    """GPU 메모리 정리"""
    import gc
    
    # Python 가비지 컬렉션 강제 실행
    gc.collect()
    
    # PyTorch GPU 캐시 정리
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        print("✅ GPU 메모리 캐시 정리 완료")

def main(qa_data: list[dict], system_message: str, hf_token: str, hf_repo_id: str, training_epochs: int) -> str:
    """메인 훈련 함수"""
    
    # 환경 변수 설정
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    # 시작 전 GPU 메모리 정리
    cleanup_gpu_memory()
    
    # 1. 모델과 토크나이저 로드
    model, tokenizer = load_model_and_tokenizer()
    
    # 2. 모델 구조 확인
    print("모델 구조 확인 중...")
    print(f"모델 타입: {type(model)}")
    
    # 3. LoRA 설정 및 적용
    lora_config = setup_lora_config(model)
    model = get_peft_model(model, lora_config)
    
    # 4. 훈련 가능한 파라미터 출력
    model.print_trainable_parameters()
    
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
        
        # 텐서로 변환
        return {
            "input_ids": torch.tensor(batch["input_ids"], dtype=torch.long),
            "attention_mask": torch.tensor(batch["attention_mask"], dtype=torch.long),
            "labels": torch.tensor(batch["labels"], dtype=torch.long)
        }
    
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
        callbacks=[early_stopping_callback],
    )
    
    # 12. 훈련 시작
    print("훈련 시작...")
    try:
        trainer.train()
        print("훈련 완료!")
    except Exception as e:
        print(f"훈련 중 오류 발생: {e}")
        
        # 더 자세한 디버깅 정보
        print("\n=== 추가 디버깅 정보 ===")
        print(f"모델 타입: {type(model)}")
        print(f"Base model 타입: {type(model.base_model) if hasattr(model, 'base_model') else 'N/A'}")
        
        # PEFT 설정 확인
        if hasattr(model, 'peft_config'):
            print(f"PEFT config: {model.peft_config}")
        
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
    
    # 17. HuggingFace 모델 URL 반환
    print(f"✅ 파인튜닝 완료! 모델 URL: {hf_model_url}")
    return hf_model_url

