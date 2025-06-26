# EXAONE 3.5 2.4B LoRA 파인튜닝 예시 코드 (수정됨)

import torch
import json
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer, 
    TrainingArguments, 
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from datasets import Dataset
import os

# GPU 설정 확인
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

class ExaoneDataPreprocessor:
    def __init__(self, tokenizer, max_length=2048):
        self.tokenizer = tokenizer
        self.max_length = max_length
        
    def create_chat_format(self, instruction, output, system_msg=None):
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

def load_model_and_tokenizer(model_name="LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"):
    """모델과 토크나이저 로드"""
    print("모델과 토크나이저 로딩 중...")
    
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
        device_map="auto",
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

def prepare_dataset(tokenizer, max_length=1024):  # max_length 줄임
    """데이터셋 준비 (예시 데이터)"""
    
    # JSON 파일에서 데이터 로드
    try:
        with open('testset.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        data_list = data['data']
        print(f"JSON 파일에서 {len(data_list)}개 데이터 로드됨")
    except FileNotFoundError:
        print("testset.json 파일을 찾을 수 없습니다. 예시 데이터를 사용합니다.")
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
    
    return tokenized_dataset

def setup_training_arguments(output_dir="./exaone-lora-results-2"):
    """훈련 인수 설정"""
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,  # 줄임
        num_train_epochs=1,  # 테스트용으로 1 에포크
        learning_rate=2e-4,  # 학습률 줄임
        lr_scheduler_type="linear",  # 더 안정적인 스케줄러
        warmup_steps=10,  # warmup_ratio 대신 steps 사용
        logging_steps=5,
        save_strategy="epoch",  # epoch마다 저장
        bf16=True,
        gradient_checkpointing=False,  # gradient_checkpointing 비활성화 (모델에서 이미 활성화함)
        dataloader_pin_memory=False,
        remove_unused_columns=False,
        report_to="none",
        seed=42,
        optim="adamw_torch",
        max_grad_norm=1.0,
        dataloader_num_workers=0,  # 멀티프로세싱 비활성화
        save_total_limit=1,
    )
    
    return training_args

def main():
    """메인 훈련 함수"""
    
    # 환경 변수 설정
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    # 1. 모델과 토크나이저 로드
    model, tokenizer = load_model_and_tokenizer()
    
    # 2. 모델 구조 확인
    print("모델 구조 확인 중...")
    print(f"모델 타입: {type(model)}")
    
    # 3. LoRA 설정 및 적용
    lora_config = setup_lora_config(model)
    model = get_peft_model(model, lora_config)
    
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
    
    # 8. 데이터 콜레이터 설정
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
        pad_to_multiple_of=8,
    )
    
    # 9. 훈련 인수 설정
    training_args = setup_training_arguments()
    
    # 10. Trainer 초기화
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=data_collator,
    )
    
    # 11. 훈련 전 gradient 테스트
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
    
    # 13. 모델 저장
    trainer.save_model()
    print(f"모델이 {training_args.output_dir}에 저장되었습니다.")

def test_finetuned_model(model_path="./exaone-lora-results-2"):
    """파인튜닝된 모델 테스트"""
    from peft import PeftModel
    
    # 베이스 모델 로드
    base_model, tokenizer = load_model_and_tokenizer()
    
    # LoRA 어댑터 로드
    model = PeftModel.from_pretrained(base_model, model_path)
    
    # 테스트 프롬프트
    test_prompt = "파이썬으로 간단한 계산기를 만드는 방법을 알려주세요."
    character_name = "루시우"
    character_personality = "자신감이 넘치는 말투를 사용하며, 대사 끝마다 '자', '어', '고' 등의 어미를 사용하여 확신에 찬 톤을 사용합니다."
    
    messages = [
        {"role": "system", "content": f"너는 {character_name} 캐릭터입니다. 사용자의 질문에 캐릭터의 성격과 어투를 반영하여 대답해주세요. 캐릭터의 성격과 어투는 {character_personality}"},
        {"role": "user", "content": test_prompt}
    ]
    
    input_ids = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to(model.device)
    
    # 생성
    with torch.no_grad():
        output = model.generate(
            input_ids,
            max_new_tokens=256,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id
        )
    
    response = tokenizer.decode(output[0], skip_special_tokens=True)
    print("생성된 응답:")
    print(response)

if __name__ == "__main__":
    main()
    