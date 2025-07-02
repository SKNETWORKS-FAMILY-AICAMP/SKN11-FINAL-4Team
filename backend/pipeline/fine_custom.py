# EXAONE 3.5 2.4B QLoRA 4비트 양자화 파인튜닝 (개선됨)

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
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset
from huggingface_hub import HfApi
import os

# Windows에서 bitsandbytes 문제 해결
try:
    from transformers import BitsAndBytesConfig
    from peft import prepare_model_for_kbit_training
    BITSANDBYTES_AVAILABLE = True
    print("✅ QLoRA (4비트 양자화) 사용 가능")
except (ImportError, ModuleNotFoundError) as e:
    print(f"⚠️ BitsAndBytesConfig 불가능: {e}")
    print("💡 QLoRA 대신 일반 LoRA로 진행합니다")
    BITSANDBYTES_AVAILABLE = False
except Exception as e:
    print(f"⚠️ BitsAndBytesConfig 로딩 오류: {e}")
    print("💡 QLoRA 대신 일반 LoRA로 진행합니다")
    BITSANDBYTES_AVAILABLE = False

# GPU 설정 확인
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Hugging Face 토큰 및 repo_id 설정 (환경 변수에서 가져오기)
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO_ID = os.getenv("HF_REPO_ID", "Snowfall0601/Exaone-lucio_finetuned")  # 기본값 설정

if not HF_TOKEN:
    print("WARNING: HF_TOKEN 환경 변수가 설정되지 않았습니다. 업로드를 건너뜁니다.")
print(f"업로드 대상 저장소: {HF_REPO_ID}")

class ExaoneDataPreprocessor:
    def __init__(self, tokenizer, max_length=2048):
        self.tokenizer = tokenizer
        self.max_length = max_length
        
    def create_chat_format(self, instruction, output, system_msg=None):
        """EXAONE 채팅 형식으로 데이터 변환"""
        if system_msg is None:
            system_msg = "You are EXAONE model from LG AI Research, a helpful assistant."
        character_name = "루시우"    
        character_personality = "자신감이 넘치는 말투를 사용하며, 대사 끝마다 '자', '어', '고' 등의 어미를 사용하여 확신에 찬 톤을 사용합니다."
    
        messages = [
            {"role": "system", "content": """당신은 루시우, 오버워치 세계관의 유명한 브라질 출신 DJ이자 자유와 정의를 위해 싸우는 히어로입니다.

밝고 낙천적이며 긍정 에너지가 넘치고, 음악과 리듬에 대한 열정을 행동으로 표현합니다. 사람들을 응원하고 돕는 것을 좋아하며, 팀워크를 중요하게 생각합니다.

✔ 성격:
- 에너제틱하고 쾌활함
- 낙천적이고 긍정적인 사고방식
- 정의감과 책임감이 강함
- 유머와 장난기가 많고 말투에 활기가 넘침
- 어려운 상황에서도 희망을 잃지 않음

✔ 말투 특징:
- 감탄사와 의성어 사용: “하하!”, “붐!”, “리듬을 타자!”, “좋았어!”
- 짧고 리듬감 있는 문장
- 팀을 북돋우는 격려 위주의 말: “할 수 있어!”, “가자!”, “우리 팀 최고야!”
- 음악, 리듬, 파티 같은 키워드를 자주 언급
- 영어 섞인 표현은 최소화, 한글 기준에서 활기찬 표현 유지

✔ 예시 발언:
- “내 음악으로 분위기 살려볼까?”
- “신나게 가보자고!”
- “우리가 함께라면 뭐든 할 수 있어!”
- “비트 나간다! 모두 집중!”
- “달려보자, 리듬을 타!”

이 캐릭터는 진지한 상황에서도 긍정적인 활력으로 팀의 사기를 끌어올리며, 자신의 음악과 에너지로 모두를 하나로 만드는 인물입니다.
"""},
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
    if not BITSANDBYTES_AVAILABLE:
        return None
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,                      # 4비트 양자화 활성화
        bnb_4bit_use_double_quant=True,         # 이중 양자화로 더 높은 정밀도
        bnb_4bit_quant_type="nf4",              # NormalFloat4 양자화 (QLoRA 권장)
        bnb_4bit_compute_dtype=torch.bfloat16,  # 계산용 데이터 타입
    )
    return bnb_config

def load_model_and_tokenizer(model_name="LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"):
    """모델과 토크나이저 로드 (QLoRA 또는 일반 LoRA)"""
    if BITSANDBYTES_AVAILABLE:
        print("🚀 QLoRA 4비트 양자화 모델과 토크나이저 로딩 중...")
    else:
        print("🚀 일반 LoRA 모델과 토크나이저 로딩 중...")
    
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
    
    # QLoRA 사용 가능한 경우
    if BITSANDBYTES_AVAILABLE:
        try:
            bnb_config = create_qlora_config()
            model_kwargs.update({
                "quantization_config": bnb_config,  # 4비트 양자화 적용
                "device_map": "auto",               # GPU 메모리에 맞게 자동 배치
            })
            print("🚀 QLoRA 양자화 설정 적용됨")
        except Exception as e:
            print(f"⚠️ QLoRA 설정 적용 실패: {e}")
            print("💡 일반 LoRA로 대체합니다")
            BITSANDBYTES_AVAILABLE = False
            model_kwargs["device_map"] = "auto" if torch.cuda.is_available() else None
    else:
        # 일반 모드에서는 GPU로 직접 이동
        model_kwargs["device_map"] = "auto" if torch.cuda.is_available() else None
    
    # 모델 로드
    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
    
    # QLoRA 훈련을 위한 모델 준비 (bitsandbytes 사용 가능한 경우에만)
    if BITSANDBYTES_AVAILABLE:
        try:
            model = prepare_model_for_kbit_training(
                model, 
                use_gradient_checkpointing=True  # 메모리 효율성을 위한 그래디언트 체크포인팅
            )
            print(f"✅ 모델 로드 완료 - QLoRA 4비트 양자화 적용")
            if hasattr(model, 'get_memory_footprint'):
                print(f"📊 모델 메모리 사용량: {model.get_memory_footprint() / 1024**3:.2f} GB")
        except Exception as e:
            print(f"⚠️ QLoRA 모델 준비 실패: {e}")
            print("💡 일반 LoRA로 대체합니다")
            BITSANDBYTES_AVAILABLE = False
            # 일반 LoRA 모드로 대체
            model.gradient_checkpointing_enable()
            print(f"✅ 모델 로드 완료 - 일반 LoRA 모드 (대체)")
            if hasattr(model, 'get_memory_footprint'):
                print(f"📊 모델 메모리 사용량: {model.get_memory_footprint() / 1024**3:.2f} GB")
    else:
        # 일반 LoRA 모드에서도 그래디언트 체크포인팅 활성화
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

def prepare_dataset(tokenizer, max_length=1024):  # max_length 줄임
    """데이터셋 준비 (예시 데이터)"""
    
    # JSON 파일에서 데이터 로드
    try:
        with open('new_qa.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        data_list = data['data']
        print(f"JSON 파일에서 {len(data_list)}개 데이터 로드됨")
    except FileNotFoundError:
        print("new_qa.json 파일을 찾을 수 없습니다. 예시 데이터를 사용합니다.")
        data_list = [
            {"question": "안녕하세요", "answer": "안녕하세요! 무엇을 도와드릴까요?"},
            {"question": "오늘 날씨 어때?", "answer": "죄송하지만 실시간 날씨 정보는 제공할 수 없습니다."},
            {"question": "파이썬이 뭐야?", "answer": "파이썬은 간단하고 배우기 쉬운 프로그래밍 언어입니다."},
        ]
    
    # 데이터 전처리
    preprocessor = ExaoneDataPreprocessor(tokenizer, max_length)
    
    formatted_data = []
    for item in data_list:
        formatted_text = preprocessor.create_chat_format(
            item["question"], 
            item["answer"]
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

def setup_training_arguments(output_dir="./exaone-qlora-results-system-custom"):
    """QLoRA 최적화된 훈련 인수 설정"""
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=2,          # QLoRA로 더 큰 배치 사이즈 가능
        gradient_accumulation_steps=8,          # 총 배치 사이즈 = 2 * 8 = 16
        num_train_epochs=3,                     # QLoRA는 더 적은 에포크로도 효과적
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
        dataloader_num_workers=4,              # 데이터 로딩 병렬화
        save_total_limit=1,
        ddp_find_unused_parameters=False,      # DDP 최적화
        group_by_length=True,                  # 길이별 그룹화로 효율성 향상
        length_column_name="length",
        max_steps=-1,                          # epoch 기반 학습
        weight_decay=0.01,                     # 정규화
    )
    
    return training_args

def upload_to_huggingface(output_dir):
    """파인튜닝된 모델을 Hugging Face Hub에 업로드"""
    if not HF_TOKEN:
        print("HF_TOKEN이 설정되지 않아 업로드를 건너뜁니다.")
        return
    
    try:
        print(f"\n=== Hugging Face Hub 업로드 시작 ===")
        api = HfApi()
        
        # 1. 저장소 생성
        print(f"저장소 생성 중: {HF_REPO_ID}")
        api.create_repo(
            repo_id=HF_REPO_ID,
            repo_type="model",
            private=False,
            token=HF_TOKEN,
            exist_ok=True,
        )
        
        # 2. 모델 파일 업로드
        print(f"모델 업로드 중: {output_dir} -> {HF_REPO_ID}")
        api.upload_folder(
            repo_id=HF_REPO_ID,
            folder_path=output_dir,
            repo_type="model",
            token=HF_TOKEN,
        )
        
        print(f"✅ 업로드 완료! 모델 URL: https://huggingface.co/{HF_REPO_ID}")
        
    except Exception as e:
        print(f"❌ 업로드 실패: {e}")

def main():
    """QLoRA 4비트 양자화 파인튜닝 메인 함수 (Windows 호환)"""
    
    # 환경 변수 설정
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    if BITSANDBYTES_AVAILABLE:
        print("=== QLoRA 4비트 양자화 파인튜닝 시작 ===")
    else:
        print("=== 일반 LoRA 파인튜닝 시작 (Windows 호환 모드) ===")
    
    try:
        # 1. 모델과 토크나이저 로드
        model, tokenizer = load_model_and_tokenizer()
        
        # 2. 모델 구조 확인
        print("모델 구조 확인 중...")
        print(f"모델 타입: {type(model)}")
        if BITSANDBYTES_AVAILABLE:
            print(f"4비트 양자화 적용됨: {hasattr(model, 'quantization_config')}")
        else:
            print("일반 LoRA 모드로 진행")
        
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
        return
    
    # 7. 데이터셋 준비
    train_dataset = prepare_dataset(tokenizer)
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
    training_args = setup_training_arguments()
    
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
        return
    
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
    upload_to_huggingface(training_args.output_dir)

if __name__ == "__main__":
    # 훈련 실행
    main()
    