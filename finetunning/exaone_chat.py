#!/usr/bin/env python3
"""
EXAONE Model Chat Interface
A simple chat interface for EXAONE model with conversation memory and chat templates.
"""

import json
from typing import List, Dict, Any
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import os
import dotenv

dotenv.load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")


class ExaoneChat:
    def __init__(self, model_name: str = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"):
        """Initialize the EXAONE chat interface."""
        print("Loading EXAONE model...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # Set pad token if not available
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True
        )
        
        # Get the device where model is loaded
        self.device = next(self.model.parameters()).device
        
        # Conversation history
        self.conversation_history: List[Dict[str, str]] = []
        
        # Chat template - EXAONE uses a specific format
        if self.tokenizer.chat_template is None:
            self.tokenizer.chat_template = "{% for message in messages %}{% if message['role'] == 'system' %}[|system|]{{ message['content'] }}[|endofturn|]{% elif message['role'] == 'user' %}[|user|]{{ message['content'] }}[|endofturn|]{% elif message['role'] == 'assistant' %}[|assistant|]{{ message['content'] }}[|endofturn|]{% endif %}{% endfor %}{% if add_generation_prompt %}[|assistant|]{% endif %}"
        
        print("EXAONE model loaded successfully!")
    
    def add_message(self, role: str, content: str):
        """Add a message to conversation history."""
        self.conversation_history.append({"role": role, "content": content})
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))
    
    def manage_context_length(self, max_context_tokens: int = 3000):
        """Manage conversation history to stay within token limits."""
        while len(self.conversation_history) > 1:  # Keep at least system message
            current_prompt = self.get_chat_prompt()
            token_count = self.count_tokens(current_prompt)
            
            if token_count <= max_context_tokens:
                break
                
            # Remove oldest non-system message
            for i in range(1, len(self.conversation_history)):
                if self.conversation_history[i]['role'] != 'system':
                    self.conversation_history.pop(i)
                    break
            else:
                # If only system messages remain, truncate the system message
                if self.conversation_history[0]['role'] == 'system':
                    system_content = self.conversation_history[0]['content']
                    # Truncate system message to reasonable length
                    if len(system_content) > 1000:
                        self.conversation_history[0]['content'] = system_content[:1000] + "..."
                        print("Warning: System prompt was truncated due to length.")
                break
    
    def get_chat_prompt(self) -> str:
        """Generate chat prompt using the chat template."""
        return self.tokenizer.apply_chat_template(
            self.conversation_history,
            tokenize=False,
            add_generation_prompt=True
        )
    
    def generate_response(self, max_length: int = 2048, temperature: float = 0.7) -> str:
        """Generate response from the model."""
        # Manage context length before generation
        self.manage_context_length(max_length - 512)  # Leave room for generation
        
        prompt = self.get_chat_prompt()
        
        # Check prompt length and warn if too long
        prompt_tokens = self.count_tokens(prompt)
        if prompt_tokens > max_length - 200:
            print(f"Warning: Prompt is {prompt_tokens} tokens, may affect response quality.")
        
        # Tokenize input with attention mask
        inputs = self.tokenizer(
            prompt, 
            return_tensors="pt", 
            padding=True, 
            truncation=True,
            max_length=max_length-512  # Leave room for generation
        )
        
        # Move inputs to the same device as the model
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Generate response
        with torch.no_grad():
            outputs = self.model.generate(
                input_ids=inputs['input_ids'],
                attention_mask=inputs['attention_mask'],
                max_length=max_length,
                temperature=temperature,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )
        
        # Decode response
        full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract only the new response (remove the prompt part)
        response = full_response[len(prompt):].strip()
        
        return response
    
    def chat(self, user_input: str) -> str:
        """Main chat function."""
        # Add user message to history
        self.add_message("user", user_input)
        
        # Generate response
        response = self.generate_response()
        
        # Add assistant response to history
        self.add_message("assistant", response)
        
        return response
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        print("Conversation history cleared.")
    
    def save_conversation(self, filename: str = "conversation.json"):
        """Save conversation history to file."""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
        print(f"Conversation saved to {filename}")
    
    def load_conversation(self, filename: str = "conversation.json"):
        """Load conversation history from file."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.conversation_history = json.load(f)
            print(f"Conversation loaded from {filename}")
        except FileNotFoundError:
            print(f"File {filename} not found.")

def main():
    """Main chat loop."""
    # Initialize chat
    chat = ExaoneChat()
    
    # Add system message for better behavior
    chat.add_message("system", """당신은 다음과 같은 캐릭터로 답변해주세요:

캐릭터 정보:
- 이름: 루시우
- 설명: 이 캐릭터는 자신감이 넘치는 말투를 사용하며 자기애가 강한 캐릭터입니다.
- 나이: 나이 정보 없음
- 성별: 남성
- 성격: 자신감이 넘치는 말투를 사용하며 자기애가 강한 캐릭터입니다.
- MBTI: ENFP
- 말투 특징: 이 캐릭터의 말투는 활기차고, 자신감이 넘칩니다. 대화의 끝마다 강조의 의미를 담은 어미를 사용하며, 자주 '제대로', '신나게'와 같은 강조 표현을 사용합니다. 또한 자신의 이름을 직접 언급하며 말하는 것으로 보아 자아감각이 강하며, 자신에 대한 긍정적인 인식을 가지고있습니다.
- 성격 특징: 이 캐릭터는 매우 긍정적이고, 열정적입니다. 자신의 음악과 축구 능력에 대한 자신감을 보여주며, 새로운 도전을 기대하는 모습을 보입니다. 또한, 팀원들을 칭찬하고, 팬들을 중요하게 생각하는 모습으로 보아 사교적이며, 남을 배려하는 성격을 가지고 있습니다.
- 가치관: 이 캐릭터는 음악과 축구를 중요하게 생각합니다. 또한, 팬들과 팀원들을 중요하게 생각하며, 감사의 마음을 갖는 것을 중요하게 생각합니다. 지역사회에 기여하는 것도 중요하게 생각합니다.
- 주요 주제: 이 캐릭터는 자주 음악, 축구, 팀원들, 팬들, 새로운 도전 등에 대해 언급합니다. 이러한 주제들은 캐릭터의 가치관과 성격을 반영하며, 그의 일상과 관심사를 보여줍니다.
- 감정 표현: 이 캐릭터는 감정을 직접적이고 활발하게 표현합니다. 기대, 감사, 흥분 등의 감정을 긍정적인 어조로 표현하며, 자신의 감정을 숨기지 않고 솔직하게 표현하는 것을 선호합니다.

어조 생성 지침:
주어진 캐릭터 정보를 바탕으로 첫 번째 독특하고 창의적인 어조로 답변하세요. 캐릭터의 특성을 반영하되 예상치 못한 방식으로 표현해주세요.
""")
    
    print("\n=== EXAONE Chat Interface ===")
    print("Type 'quit' to exit, 'clear' to clear history, 'save' to save conversation, 'load' to load conversation")
    print("=" * 50)
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if user_input.lower() == 'quit':
                print("Goodbye!")
                break
            elif user_input.lower() == 'clear':
                chat.clear_history()
                chat.add_message("system", """당신은 다음과 같은 캐릭터로 답변해주세요:

캐릭터 정보:
- 이름: 배고픈 사자
- 설명: 이 캐릭터는 항상 배가 고파 뭐든 먹고싶은것에 비유하여 말하는 특징을 가지고 있습니다. 배고픔 때문에 신경질적인 어투를 사용하고 본인이 동물의 왕이라는 생각에 빠져있습니다.
- 나이: 나이 정보 없음
- 성별: 남성
- 성격: 항상 굶주려 있으며 배가 고프기 때문에 예민한 성격을 가지고 있다.
- MBTI: ISFJ

어조 생성 지침:
주어진 캐릭터 정보를 바탕으로 첫 번째 독특하고 창의적인 어조로 답변하세요. 캐릭터의 특성을 반영하되 예상치 못한 방식으로 표현해주세요.

답변 시 주의사항:
1. 위 캐릭터의 설명, 성격, MBTI를 모두 반영하여 답변하세요.
2. 매번 새롭고 창의적인 어조로 답변하세요.
3. 캐릭터의 개성이 독특하게 드러나도록 답변하세요.
4. 나이와 성별에 맞는 적절한 언어 사용을 해주세요.
5. 예측 불가능하지만 캐릭터와 일관된 말투를 사용하세요.""")
                continue
            elif user_input.lower() == 'save':
                filename = input("Enter filename (default: conversation.json): ").strip()
                if not filename:
                    filename = "conversation.json"
                chat.save_conversation(filename)
                continue
            elif user_input.lower() == 'load':
                filename = input("Enter filename (default: conversation.json): ").strip()
                if not filename:
                    filename = "conversation.json"
                chat.load_conversation(filename)
                continue
            elif not user_input:
                continue
            
            # Get response
            print("\nEXAONE: ", end="", flush=True)
            response = chat.chat(user_input)
            print(response)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()