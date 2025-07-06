# EXAONE 3.5 2.4B QLoRA 4비트 양자화 파인튜닝 (개선됨)

import torch
import json
from typing import List, Dict
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer, 
    TrainingArguments, 
    Trainer,
    DataCollatorForLanguageModeling,
    EarlyStoppingCallback
)
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset
from huggingface_hub import HfApi
import os

# GPU 설정 확인
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

class ExaoneDataPreprocessor:
    def __init__(self, tokenizer, max_length=2048):
        self.tokenizer = tokenizer
        self.max_length = max_length
        
    def create_chat_format(self, instruction, output, system_msg: str = None):
        """EXAONE 채팅 형식으로 데이터 변환"""
        if system_msg is None:
            system_msg = "You are EXAONE model from LG AI Research, a helpful assistant."
        
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

def create_qlora_config():
    """QLoRA를 위한 4비트 양자화 설정 생성 (bitsandbytes 사용 가능한 경우에만)"""

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,                      # 4비트 양자화 활성화
        bnb_4bit_use_double_quant=True,         # 이중 양자화로 더 높은 정밀도
        bnb_4bit_quant_type="nf4",              # NormalFloat4 양자화 (QLoRA 권장)
        bnb_4bit_compute_dtype=torch.bfloat16,  # 계산용 데이터 타입
    )
    return bnb_config

def load_model_and_tokenizer(model_name="LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"):
    """모델과 토크나이저 로드 (QLoRA 또는 일반 LoRA)"""
    
    # 토크나이저 로드
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    # 패딩 토큰 설정 (필요한 경우)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    # 모델 로드 파라미터 설정
    model_kwargs = {
        "torch_dtype": torch.bfloat16,
        "trust_remote_code": True,
        "use_cache": False,  # 그래디언트 체크포인팅과 호환성을 위해
    }
    

    model_kwargs["device_map"] = "auto" if torch.cuda.is_available() else None
    
    # 모델 로드
    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
    
    # QLoRA 훈련을 위한 모델 준비 (bitsandbytes 사용 가능한 경우에만)
    model.gradient_checkpointing_enable()
    print(f"✅ 모델 로드 완료 - 일반 LoRA 모드")
    if hasattr(model, 'get_memory_footprint'):
        print(f"📊 모델 메모리 사용량: {model.get_memory_footprint() / 1024**3:.2f} GB")
    
    return model, tokenizer

def setup_qlora_config(model):
    """QLoRA 전용 LoRA 설정 - 4비트 양자화에 최적화"""
    
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
    
    print(f"QLoRA에 사용할 모듈들: {attention_modules}")
    
    # QLoRA 최적화된 설정
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,                           # QLoRA에서는 더 높은 rank 사용 가능 (4비트 양자화로 메모리 절약)
        lora_alpha=32,                  # alpha = 2 * r (QLoRA 권장 설정)
        lora_dropout=0.1,              # 약간 높은 dropout으로 overfitting 방지
        target_modules=attention_modules,
        bias="none",                   # 4비트 양자화와 호환성을 위해 bias 사용 안함
        use_rslora=True,               # RSLoRA 사용으로 성능 향상
        init_lora_weights="gaussian",  # 가우시안 초기화로 안정성 향상
    )
    return lora_config

# 하위 호환성을 위한 별칭
def setup_lora_config(model):
    """하위 호환성을 위한 별칭 - QLoRA 설정 사용"""
    return setup_qlora_config(model)

def prepare_dataset(tokenizer, qa_data: List[Dict], system_message: str, max_length=1024):  # max_length 줄임
    """데이터셋 준비 (예시 데이터)"""
    
    # 데이터 전처리
    preprocessor = ExaoneDataPreprocessor(tokenizer, max_length)
    
    formatted_data = []
    for item in qa_data:
        formatted_text = preprocessor.create_chat_format(
            item.get('question', '').strip(), 
            item.get('answer', '').strip(),
            system_msg=system_message
        )
        formatted_data.append({"text": formatted_text})
    
    # Dataset 객체 생성
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
        if isinstance(example["input_ids"], list) and isinstance(example["labels"], list):
            # 정상적인 경우 그대로 반환
            return example
        else:
            # 문제가 있는 경우 수정
            if not isinstance(example["input_ids"], list):
                example["input_ids"] = example["input_ids"].tolist() if hasattr(example["input_ids"], "tolist") else [example["input_ids"]]
            if not isinstance(example["labels"], list):
                example["labels"] = example["labels"].tolist() if hasattr(example["labels"], "tolist") else [example["labels"]]
            return example
    
    tokenized_dataset = tokenized_dataset.map(validate_and_fix_data)
    
    return tokenized_dataset

def setup_training_arguments(output_dir="./exaone-qlora-results-system-custom", training_epochs: int = 3):
    """QLoRA 최적화된 훈련 인수 설정"""
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=2,          # QLoRA로 더 큰 배치 사이즈 가능
        gradient_accumulation_steps=8,          # 총 배치 사이즈 = 2 * 8 = 16
        num_train_epochs=training_epochs,       # QLoRA는 더 적은 에포크로도 효과적
        learning_rate=5e-5,                     # QLoRA 권장 학습률 (더 낮게)
        lr_scheduler_type="cosine",             # Cosine 스케줄러로 더 부드러운 학습
        warmup_steps=50,                        # 더 긴 warmup
        logging_steps=10,
        save_strategy="epoch",                  # epoch마다 저장
        eval_strategy="epoch",                  # 조기 종료를 위한 평가 전략
        load_best_model_at_end=True,           # 최적 모델 로드
        metric_for_best_model="loss",          # 최적 모델 기준
        greater_is_better=False,               # loss는 낮을수록 좋음
        bf16=True,                             # 4비트 양자화와 함께 bf16 사용
        gradient_checkpointing=True,           # 메모리 효율성을 위해 활성화
        dataloader_pin_memory=False,
        remove_unused_columns=False,
        report_to="none",
        seed=42,
        optim="paged_adamw_8bit",              # QLoRA 최적화된 옵티마이저
        max_grad_norm=0.3,                     # QLoRA 권장 gradient clipping
        dataloader_num_workers=0,              # 데이터 로딩 병렬화
        save_total_limit=1,
        ddp_find_unused_parameters=False,      # DDP 최적화
        group_by_length=True,                  # 길이별 그룹화로 효율성 향상
        length_column_name="length",
        max_steps=-1,                          # epoch 기반 학습
        weight_decay=0.01,                     # 정규화
    )
    
    return training_args

def upload_to_huggingface(output_dir: str, hf_token: str, hf_repo_id: str):
    """파인튜닝된 모델을 Hugging Face Hub에 업로드"""
    if not hf_token:
        print("HF 토큰이 제공되지 않아 업로드를 건너뜁니다.")
        return
    
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
        return f"https://huggingface.co/{hf_repo_id}"
        
    except Exception as e:
        print(f"❌ 업로드 실패: {e}")
        return None

class DataCollator:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def __call__(self, features):
        for f in features:
            f["input_ids"] = list(f["input_ids"])
            f["labels"] = list(f["labels"])
        max_length = max(len(f["input_ids"]) for f in features)
        batch = {
            "input_ids": [],
            "attention_mask": [],
            "labels": []
        }
        for feature in features:
            input_ids = feature["input_ids"]
            labels = feature["labels"]
            padding_length = max_length - len(input_ids)
            padded_input_ids = input_ids + [self.tokenizer.pad_token_id] * padding_length
            attention_mask = [1] * len(input_ids) + [0] * padding_length
            padded_labels = labels + [-100] * padding_length
            batch["input_ids"].append(padded_input_ids)
            batch["attention_mask"].append(attention_mask)
            batch["labels"].append(padded_labels)
        return {
            "input_ids": torch.tensor(batch["input_ids"], dtype=torch.long),
            "attention_mask": torch.tensor(batch["attention_mask"], dtype=torch.long),
            "labels": torch.tensor(batch["labels"], dtype=torch.long)
        }

def main(qa_data: List[Dict], system_message: str, hf_token: str, hf_repo_id: str, training_epochs: int = 3, output_dir: str = "./exaone-qlora-results-system-custom"):
    """QLoRA 4비트 양자화 파인튜닝 메인 함수 (Windows 호환)"""
    
    # 환경 변수 설정
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    print(hf_token)
    try:
        # 1. 모델과 토크나이저 로드
        model, tokenizer = load_model_and_tokenizer()
        
        # 2. 모델 구조 확인
        print("모델 구조 확인 중...")
        print(f"모델 타입: {type(model)}")
        
        # 3. LoRA 설정 및 적용
        lora_config = setup_qlora_config(model)  # QLoRA 설정이지만 bitsandbytes 없으면 일반 LoRA로 동작
        model = get_peft_model(model, lora_config)
    
    except Exception as e:
        print(f"❌ 모델 로딩 중 오류: {e}")
        print("💡 오류 해결 방법:")
        print("  1. requirements.txt의 패키지들이 모두 설치되었는지 확인")
        print("  2. Windows에서는 bitsandbytes 대신 일반 LoRA를 사용합니다")
        print("  3. GPU 메모리가 충분한지 확인하세요")
        raise
    
    # 4. LoRA 적용 후 gradient checkpointing 다시 활성화
    if hasattr(model, 'enable_input_require_grads'):
        model.enable_input_require_grads()
    
    # 5. 훈련 가능한 파라미터 출력
    model.print_trainable_parameters()
    
    # 6. gradient 체크 - 더 자세한 확인
    print("\nGradient 설정 확인:")
    trainable_params = 0
    all_params = 0
    
    for name, param in model.named_parameters():
        all_params += param.numel()
        if param.requires_grad:
            trainable_params += param.numel()
            print(f"  ✓ {name}: {param.shape} (requires_grad=True)")
        else:
            print(f"  ✗ {name}: {param.shape} (requires_grad=False)")
    
    print(f"총 파라미터: {all_params:,}")
    print(f"훈련 가능한 파라미터: {trainable_params:,}")
    print(f"훈련 가능 비율: {100 * trainable_params / all_params:.4f}%")
    
    if trainable_params == 0:
        print("ERROR: 훈련 가능한 파라미터가 없습니다!")
        return None
    
    # 7. 데이터셋 준비
    train_dataset = prepare_dataset(tokenizer, qa_data, system_message)
    print(f"훈련 데이터셋 크기: {len(train_dataset)}")
    
    # 데이터셋을 train/eval로 분할 (조기 종료를 위한 validation 데이터 필요)
    train_size = int(0.8 * len(train_dataset))
    eval_size = len(train_dataset) - train_size
    
    train_dataset_split = train_dataset.select(range(train_size))
    eval_dataset = train_dataset.select(range(train_size, train_size + eval_size))
    
    print(f"훈련 데이터: {len(train_dataset_split)}, 검증 데이터: {len(eval_dataset)}")
    
    # 8. 데이터 콜레이터 설정 - 더 안전한 방식 (함수는 이미 global scope에 있음)
    
    # 9. 훈련 인수 설정 (기존 로직대로)
    training_args = setup_training_arguments(output_dir=output_dir, training_epochs=training_epochs)
    
    # 10. 조기 종료 콜백 설정
    early_stopping_callback = EarlyStoppingCallback(
        early_stopping_patience=2,  # 2 epoch 동안 개선이 없으면 종료
        early_stopping_threshold=0.01  # 최소 개선 임계값
    )
    
    # 11. Trainer 초기화
    data_collator = DataCollator(tokenizer)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset_split,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
        callbacks=[early_stopping_callback],
    )
    
    # 12. 훈련 전 gradient 테스트
    print("\n=== 훈련 전 Gradient 테스트 ===")
    model.train()
    sample_batch = next(iter(trainer.get_train_dataloader()))
    sample_batch = {k: v.to(model.device) for k, v in sample_batch.items()}
    
    # Forward pass
    outputs = model(**sample_batch)
    loss = outputs.loss
    print(f"Forward pass 성공, loss: {loss.item()}")
    
    # Backward pass 테스트
    try:
        loss.backward()
        print("Backward pass 성공!")
        
        # Gradient 확인
        grad_found = False
        for name, param in model.named_parameters():
            if param.requires_grad and param.grad is not None:
                print(f"  Gradient found: {name}")
                grad_found = True
                break
        
        if not grad_found:
            print("WARNING: Gradient가 계산되지 않았습니다!")
        
        # Gradient 초기화
        model.zero_grad()
        
    except Exception as e:
        print(f"Backward pass 실패: {e}")
        return None
    
    # 13. QLoRA 훈련 시작
    print("=== QLoRA 4비트 양자화 훈련 시작 ===")
    try:
        # 메모리 사용량 출력
        if torch.cuda.is_available():
            print(f"GPU 메모리 사용량 (훈련 전): {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
        
        trainer.train()
        
        if torch.cuda.is_available():
            print(f"GPU 메모리 사용량 (훈련 후): {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
        
        print("🎉 QLoRA 4비트 양자화 훈련 완료!")
        
    except Exception as e:
        print(f"❌ QLoRA 훈련 중 오류 발생: {e}")
        
        # 더 자세한 디버깅 정보
        print("\n=== QLoRA 디버깅 정보 ===")
        print(f"모델 타입: {type(model)}")
        print(f"Base model 타입: {type(model.base_model) if hasattr(model, 'base_model') else 'N/A'}")
        print(f"4비트 양자화: {hasattr(model.base_model, 'quantization_config') if hasattr(model, 'base_model') else 'N/A'}")
        
        # PEFT 설정 확인
        if hasattr(model, 'peft_config'):
            print(f"PEFT config: {model.peft_config}")
        
        # GPU 메모리 정보
        if torch.cuda.is_available():
            print(f"GPU 메모리: {torch.cuda.memory_allocated() / 1024**3:.2f} GB / {torch.cuda.memory_reserved() / 1024**3:.2f} GB")
        
        raise
    
    # 14. 모델 저장
    trainer.save_model()
    print(f"모델이 {training_args.output_dir}에 저장되었습니다.")
    
    # 15. Hugging Face Hub에 업로드
    model_url = upload_to_huggingface(training_args.output_dir, hf_token, hf_repo_id)
    return model_url