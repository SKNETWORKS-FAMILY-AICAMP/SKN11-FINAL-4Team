# EXAONE 파인튜닝 모델 채팅 인터페이스

import torch
import json
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import os

class ExaoneChatBot:
    def __init__(self, base_model_name="LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct", 
                 lora_path="./exaone-lora-results-3"):
        """
        EXAONE 채팅봇 초기화
        
        Args:
            base_model_name: 베이스 모델 이름
            lora_path: LoRA 어댑터가 저장된 경로
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Device: {self.device}")
        
        # 캐릭터 설정
        self.character_name = "루시우"
        self.character_personality = "자신감이 넘치는 말투를 사용하며 자기애가 강한 캐릭터입니다."
        
        # 대화 히스토리
        self.conversation_history = []
        
        # 모델과 토크나이저 로드
        self.load_model(base_model_name, lora_path)
        
    def load_model(self, base_model_name, lora_path):
        """모델과 토크나이저 로드"""
        print("모델 로딩 중...")
        
        # 토크나이저 로드
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
            
            # LoRA 어댑터 로드 및 병합
            if os.path.exists(lora_path):
                print(f"LoRA 어댑터 로딩: {lora_path}")
                self.model = PeftModel.from_pretrained(base_model, lora_path)
                
                # 선택사항: LoRA 가중치를 베이스 모델에 병합 (추론 속도 향상)
                print("LoRA 가중치를 베이스 모델에 병합 중...")
                self.model = self.model.merge_and_unload()
            else:
                print(f"LoRA 어댑터를 찾을 수 없습니다: {lora_path}")
                print("베이스 모델만 사용합니다.")
                self.model = base_model
                
        except Exception as e:
            print(f"모델 로딩 중 오류: {e}")
            raise
        
        # 모델을 평가 모드로 설정
        self.model.eval()
        print("모델 로딩 완료!")
    
    def create_system_message(self):
        """시스템 메시지 생성"""
        return f"당신은 {self.character_name} 입니다 사용자를 부를때 루시우 지칭하지 마세요. 사용자의 질문에 캐릭터의 성격과 어투를 반영하여 대답해주세요. 캐릭터의 성격과 어투는 {self.character_personality}"
    
    def format_conversation(self, user_input, include_history=True):
        """대화를 채팅 형식으로 포맷"""
        messages = [{"role": "system", "content": self.create_system_message()}]
        
        # 대화 히스토리 포함 (선택사항)
        if include_history:
            for turn in self.conversation_history[-5:]:  # 최근 5턴만 포함
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
        self.conversation_history.append({
            "user": user_input,
            "assistant": response
        })
        
        return response
    
    def clear_history(self):
        """대화 히스토리 초기화"""
        self.conversation_history = []
        print("대화 히스토리가 초기화되었습니다.")
    
    def save_conversation(self, filename="conversation.json"):
        """대화 내용 저장"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
            print(f"대화 내용이 {filename}에 저장되었습니다.")
        except Exception as e:
            print(f"저장 중 오류: {e}")
    
    def load_conversation(self, filename="conversation.json"):
        """대화 내용 불러오기"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.conversation_history = json.load(f)
            print(f"{filename}에서 대화 내용을 불러왔습니다.")
        except FileNotFoundError:
            print(f"{filename} 파일을 찾을 수 없습니다.")
        except Exception as e:
            print(f"불러오기 중 오류: {e}")

def interactive_chat():
    """대화형 채팅 인터페이스"""
    print("=" * 60)
    print("🤖 EXAONE 루시우 채팅봇")
    print("=" * 60)
    print("명령어:")
    print("  /clear    - 대화 히스토리 초기화")
    print("  /save     - 대화 내용 저장")
    print("  /load     - 대화 내용 불러오기")
    print("  /exit     - 종료")
    print("  /help     - 도움말")
    print("=" * 60)
    
    # 채팅봇 초기화
    try:
        chatbot = ExaoneChatBot()
    except Exception as e:
        print(f"채팅봇 초기화 실패: {e}")
        return
    
    print(f"\n💬 {chatbot.character_name}와 대화를 시작합니다!")
    print("안녕하세요! 무엇을 도와드릴까요?")
    
    while True:
        try:
            # 사용자 입력
            user_input = input("\n👤 You: ").strip()
            
            if not user_input:
                continue
            
            # 명령어 처리
            if user_input.startswith('/'):
                command = user_input[1:].lower()
                
                if command == 'exit':
                    print("대화를 종료합니다. 안녕히 가세요!")
                    break
                elif command == 'clear':
                    chatbot.clear_history()
                    continue
                elif command == 'save':
                    filename = input("저장할 파일명 (기본값: conversation.json): ").strip()
                    if not filename:
                        filename = "conversation.json"
                    chatbot.save_conversation(filename)
                    continue
                elif command == 'load':
                    filename = input("불러올 파일명 (기본값: conversation.json): ").strip()
                    if not filename:
                        filename = "conversation.json"
                    chatbot.load_conversation(filename)
                    continue
                elif command == 'help':
                    print("\n명령어:")
                    print("  /clear    - 대화 히스토리 초기화")
                    print("  /save     - 대화 내용 저장")
                    print("  /load     - 대화 내용 불러오기")
                    print("  /exit     - 종료")
                    print("  /help     - 도움말")
                    continue
                else:
                    print("알 수 없는 명령어입니다. /help를 입력하여 도움말을 확인하세요.")
                    continue
            
            # 응답 생성
            print(f"\n🤖 {chatbot.character_name}: ", end="", flush=True)
            response = chatbot.chat_turn(user_input)
            print(response)
            
        except KeyboardInterrupt:
            print("\n\n대화를 종료합니다. 안녕히 가세요!")
            break
        except Exception as e:
            print(f"\n오류가 발생했습니다: {e}")
            continue

def batch_chat(questions, lora_path="./exaone-lora-results-3"):
    """여러 질문을 한 번에 처리하는 배치 모드"""
    chatbot = ExaoneChatBot(lora_path=lora_path)
    
    results = []
    for i, question in enumerate(questions, 1):
        print(f"\n질문 {i}: {question}")
        response = chatbot.chat_turn(question)
        print(f"답변 {i}: {response}")
        
        results.append({
            "question": question,
            "response": response
        })
    
    return results

# 사용 예시
if __name__ == "__main__":
    # 대화형 모드 실행
    interactive_chat()
    
    # 배치 모드 예시 (주석 처리됨)
    """
    sample_questions = [
        "안녕하세요!",
        "파이썬으로 간단한 계산기를 만드는 방법을 알려주세요.",
        "오늘 기분이 어떠세요?",
        "프로그래밍을 배우는 좋은 방법이 있을까요?"
    ]
    
    results = batch_chat(sample_questions)
    
    # 결과 저장
    with open("batch_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    """
