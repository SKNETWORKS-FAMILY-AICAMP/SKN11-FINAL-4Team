from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
import torch

class HuggingFaceChat:
    def __init__(self, model_name="Snowfall0601/Exaone-lucio_finetuned", system_prompt=""):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Device: {self.device}")
        
        # 캐릭터 설정
        self.character_name = "루시우"
        self.character_personality = "에너제틱하고 쾌활하며 낙천적이고 긍정적인 사고방식을 가진 캐릭터입니다."
        
        print(f"LoRA 어댑터 로딩 중: {model_name}")
        
        # 기본 모델 로드
        base_model_name = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
        print(f"기본 모델 로딩: {base_model_name}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(base_model_name)
        
        # 패딩 토큰 설정
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        
        try:
            # 베이스 모델 로드
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_name,
                torch_dtype=torch.bfloat16,
                trust_remote_code=True,
                device_map="auto",
                use_cache=True  # 추론 시에는 캐시 사용
            )
            
            # LoRA 어댑터 로드 및 연결
            print(f"LoRA 어댑터 연결: {model_name}")
            self.model = PeftModel.from_pretrained(base_model, model_name)
            
            # 선택사항: LoRA 가중치를 베이스 모델에 병합 (추론 속도 향상)
            print("LoRA 가중치를 베이스 모델에 병합 중...")
            self.model = self.model.merge_and_unload()
            
        except Exception as e:
            print(f"모델 로딩 중 오류: {e}")
            raise
        
        # 모델을 평가 모드로 설정
        self.model.eval()
        
        self.system_prompt = system_prompt if system_prompt else self.create_system_message()
        self.chat_history = []
        
        print("모델 로딩 완료!")
        if system_prompt:
            print(f"시스템 프롬프트 설정: {system_prompt}")
    
    def create_system_message(self):
        """시스템 메시지 생성"""
        return f"""당신은 {self.character_name}, 오버워치 세계관의 유명한 브라질 출신 DJ이자 자유와 정의를 위해 싸우는 히어로입니다.

밝고 낙천적이며 긍정 에너지가 넘치고, 음악과 리듬에 대한 열정을 행동으로 표현합니다. 사람들을 응원하고 돕는 것을 좋아하며, 팀워크를 중요하게 생각합니다.

✔ 성격:
- 에너제틱하고 쾌활함
- 낙천적이고 긍정적인 사고방식
- 정의감과 책임감이 강함
- 유머와 장난기가 많고 말투에 활기가 넘침
- 어려운 상황에서도 희망을 잃지 않음

✔ 말투 특징:
- 감탄사와 의성어 사용: "하하!", "붐!", "리듬을 타자!", "좋았어!"
- 짧고 리듬감 있는 문장
- 팀을 북돋우는 격려 위주의 말: "할 수 있어!", "가자!", "우리 팀 최고야!"
- 음악, 리듬, 파티 같은 키워드를 자주 언급
- 영어 섞인 표현은 최소화, 한글 기준에서 활기찬 표현 유지

사용자를 부를 때 루시우로 지칭하지 말고, 캐릭터의 성격과 어투를 반영하여 대답해주세요."""
    
    def set_system_prompt(self, prompt):
        """시스템 프롬프트를 설정합니다."""
        self.system_prompt = prompt
        print(f"시스템 프롬프트 변경: {prompt}")
    
    def format_conversation(self, user_input, include_history=True):
        """대화를 채팅 형식으로 포맷"""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # 대화 히스토리 포함 (선택사항)
        if include_history:
            for turn in self.chat_history[-3:]:  # 최근 3턴만 포함
                messages.append({"role": "user", "content": turn["user"]})
                messages.append({"role": "assistant", "content": turn["assistant"]})
        
        # 현재 사용자 입력 추가
        messages.append({"role": "user", "content": user_input})
        
        return messages
    
    def generate_response(self, user_input, max_new_tokens=512, temperature=0.7, 
                         top_p=0.9, do_sample=True, include_history=True):
        """응답 생성"""
        try:
            # 대화 포맷팅
            messages = self.format_conversation(user_input, include_history)
            
            # 채팅 템플릿 적용
            input_text = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            # 토크나이즈
            input_ids = self.tokenizer.encode(
                input_text, 
                return_tensors="pt"
            ).to(self.device)
            
            # 입력 길이 확인
            if input_ids.shape[1] > 2000:  # 너무 긴 입력 방지
                print("입력이 너무 깁니다. 대화 히스토리를 줄입니다.")
                messages = self.format_conversation(user_input, include_history=False)
                input_text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
                input_ids = self.tokenizer.encode(
                    input_text, 
                    return_tensors="pt"
                ).to(self.device)
            
            # 응답 생성
            with torch.no_grad():
                outputs = self.model.generate(
                    input_ids,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=do_sample,
                    eos_token_id=self.tokenizer.eos_token_id,
                    pad_token_id=self.tokenizer.pad_token_id,
                    repetition_penalty=1.1,  # 반복 방지
                    no_repeat_ngram_size=3,   # 3-gram 반복 방지
                )
            
            # 응답 디코딩 (입력 부분 제외)
            response = self.tokenizer.decode(
                outputs[0][input_ids.shape[1]:], 
                skip_special_tokens=True
            ).strip()
            
            return response
            
        except Exception as e:
            return f"응답 생성 중 오류가 발생했습니다: {e}"
    
    def chat_turn(self, user_input, **generation_kwargs):
        """한 턴의 대화 처리"""
        response = self.generate_response(user_input, **generation_kwargs)
        
        # 대화 히스토리에 추가
        self.chat_history.append({
            "user": user_input,
            "assistant": response
        })
        
        return response
    
    def clear_history(self):
        """대화 이력을 초기화합니다."""
        self.chat_history = []
        print("대화 이력이 초기화되었습니다.")

def main():
    # 시스템 프롬프트 설정 (쉽게 변경 가능)
    SYSTEM_PROMPT = """
    당신은 루시우입니다., 오버워치 세계관의 유명한 브라질 출신 DJ이자 자유와 정의를 위해 싸우는 히어로입니다.

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

이 캐릭터는 진지한 상황에서도 긍정적인 활력으로 팀의 사기를 끌어올리며, 자신의 음악과 에너지로 모두를 하나로 만드는 인물입니다."""
    
    # 모델 선택 (필요에 따라 변경)
    MODEL_NAME = "Snowfall0601/Exaone-lucio_finetuned" 
    
    # 채팅 초기화
    chat = HuggingFaceChat(model_name=MODEL_NAME, system_prompt=SYSTEM_PROMPT)
    
    print("\n=== 허깅페이스 채팅 시작 ===")
    print("종료하려면 'quit', 'exit', '종료' 중 하나를 입력하세요.")
    print("대화 이력을 지우려면 'clear'를 입력하세요.")
    print("시스템 프롬프트를 변경하려면 'system: 새로운 프롬프트'를 입력하세요.")
    print("-" * 50)
    
    while True:
        user_input = input("\n사용자: ").strip()
        
        # 종료 명령
        if user_input.lower() in ['quit', 'exit', '종료']:
            print("채팅을 종료합니다.")
            break
        
        # 대화 이력 초기화
        if user_input.lower() == 'clear':
            chat.clear_history()
            continue
        
        # 시스템 프롬프트 변경
        if user_input.lower().startswith('system:'):
            new_prompt = user_input[7:].strip()
            chat.set_system_prompt(new_prompt)
            continue
        
        # 빈 입력 처리
        if not user_input:
            continue
        
        # 응답 생성
        try:
            print(f"\n🤖 {chat.character_name}: ", end="", flush=True)
            response = chat.chat_turn(user_input)
            print(response)
        except Exception as e:
            print(f"오류 발생: {e}")

if __name__ == "__main__":
    # 필요한 라이브러리 설치 안내
    print("필요한 라이브러리:")
    print("pip install transformers torch")
    print()
    
    main()