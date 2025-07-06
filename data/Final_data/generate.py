import os
import json
import time
from typing import List, Dict, Optional, Union
import torch
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    pipeline,
    BitsAndBytesConfig
)
import logging
from datetime import datetime
import argparse
import gc

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'dataset_generation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

class HuggingFaceKnowledgeDatasetGenerator:
    def __init__(self, 
                 dialogue_samples: List[str], 
                 character_name: str = "캐릭터",
                 model_name: str = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct",
                 use_4bit: bool = True,
                 max_length: int = 512,
                 device: str = "auto"):
        """
        Args:
            dialogue_samples: 캐릭터의 대사 샘플 리스트
            character_name: 캐릭터 이름 (메타데이터용)
            model_name: 허깅페이스 모델 이름
            use_4bit: 4비트 양자화 사용 여부 (메모리 절약)
            max_length: 최대 생성 길이
            device: 사용할 디바이스 ('auto', 'cuda', 'cpu')
        """
        self.dialogue_samples = dialogue_samples
        self.character_name = character_name
        self.model_name = model_name
        self.max_length = max_length
        
        # 디바이스 설정
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logging.info(f"사용 디바이스: {self.device}")
        logging.info(f"사용 모델: {model_name}")
        
        # 모델 및 토크나이저 로드
        self.tokenizer, self.model, self.use_device_map = self.load_model(use_4bit)
        
        # 텍스트 생성 파이프라인 설정
        self.generator = self.create_pipeline()
        
        # 캐릭터 특성 분석
        self.character_traits = self.analyze_character_traits()
        
    def load_model(self, use_4bit: bool = True):
        """허깅페이스 모델 로드"""
        try:
            # 토크나이저 로드
            tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # 패딩 토큰 설정
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            use_device_map = False
            
            # 4비트 양자화 설정 (메모리 절약)
            if use_4bit and self.device == "cuda":
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
                
                model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    quantization_config=quantization_config,
                    device_map="auto",
                    trust_remote_code=True
                )
                use_device_map = True
            else:
                if self.device == "cuda":
                    model = AutoModelForCausalLM.from_pretrained(
                        self.model_name,
                        torch_dtype=torch.float16,
                        device_map="auto",
                        trust_remote_code=True
                    )
                    use_device_map = True
                else:
                    model = AutoModelForCausalLM.from_pretrained(
                        self.model_name,
                        torch_dtype=torch.float32,
                        trust_remote_code=True
                    )
                    model = model.to(self.device)
                    use_device_map = False
            
            logging.info(f"모델 로드 완료: {self.model_name}")
            logging.info(f"Device map 사용: {use_device_map}")
            return tokenizer, model, use_device_map
            
        except Exception as e:
            logging.error(f"모델 로드 실패: {e}")
            # 대안 모델들 시도
            fallback_models = [
                "microsoft/DialoGPT-small",
                "gpt2",
                "skt/kogpt2-base-v2"  # 한국어 모델
            ]
            
            for fallback_model in fallback_models:
                try:
                    logging.info(f"대안 모델 시도: {fallback_model}")
                    tokenizer = AutoTokenizer.from_pretrained(fallback_model)
                    if tokenizer.pad_token is None:
                        tokenizer.pad_token = tokenizer.eos_token
                        
                    if self.device == "cuda":
                        model = AutoModelForCausalLM.from_pretrained(
                            fallback_model,
                            torch_dtype=torch.float16,
                            device_map="auto"
                        )
                        use_device_map = True
                    else:
                        model = AutoModelForCausalLM.from_pretrained(
                            fallback_model,
                            torch_dtype=torch.float32
                        )
                        model = model.to(self.device)
                        use_device_map = False
                        
                    logging.info(f"대안 모델 로드 성공: {fallback_model}")
                    self.model_name = fallback_model
                    return tokenizer, model, use_device_map
                    
                except Exception as fallback_e:
                    logging.warning(f"대안 모델 {fallback_model} 로드 실패: {fallback_e}")
                    continue
            
            raise Exception("모든 모델 로드 시도 실패")
    
    def create_pipeline(self):
        """파이프라인 생성"""
        try:
            # device_map을 사용한 경우 파이프라인에서 디바이스를 지정하지 않음
            if self.use_device_map:
                generator = pipeline(
                    "text-generation",
                    model=self.model,
                    tokenizer=self.tokenizer,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
                )
            else:
                generator = pipeline(
                    "text-generation",
                    model=self.model,
                    tokenizer=self.tokenizer,
                    device=0 if self.device == "cuda" else -1,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
                )
            
            logging.info("텍스트 생성 파이프라인 초기화 완료")
            return generator
            
        except Exception as e:
            logging.error(f"파이프라인 생성 실패: {e}")
            raise
    
    def generate_text(self, prompt: str, max_new_tokens: int = 100, temperature: float = 0.8) -> str:
        """텍스트 생성"""
        try:
            # 프롬프트 길이 제한
            encoded = self.tokenizer.encode(prompt, return_tensors="pt")
            if encoded.shape[1] > self.max_length - max_new_tokens:
                # 프롬프트가 너무 길면 자름
                encoded = encoded[:, -(self.max_length - max_new_tokens):]
                prompt = self.tokenizer.decode(encoded[0], skip_special_tokens=True)
            
            # 텍스트 생성
            outputs = self.generator(
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.9,
                top_k=50,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                repetition_penalty=1.1
            )
            
            # 결과에서 원본 프롬프트 제거
            generated_text = outputs[0]['generated_text']
            if generated_text.startswith(prompt):
                generated_text = generated_text[len(prompt):].strip()
            
            return generated_text
            
        except Exception as e:
            logging.error(f"텍스트 생성 실패: {e}")
            return ""
    
    def analyze_character_traits(self) -> Dict[str, any]:
        """대사를 분석하여 캐릭터 특성 추출"""
        try:
            sample_text = "\n".join(self.dialogue_samples[:10])
            
            prompt = f"""다음 대사들을 분석하여 캐릭터의 특징을 간단히 정리하세요:

{sample_text}

분석 결과:
1. 말투: """
            
            analysis = self.generate_text(prompt, max_new_tokens=200, temperature=0.3)
            
            traits = {
                "analysis": analysis if analysis else "분석 결과 없음",
                "sample_count": len(self.dialogue_samples),
                "model_used": self.model_name
            }
            
            logging.info(f"캐릭터 특성 분석 완료")
            return traits
            
        except Exception as e:
            logging.error(f"캐릭터 특성 분석 실패: {e}")
            return {
                "analysis": "분석 실패", 
                "sample_count": len(self.dialogue_samples),
                "model_used": self.model_name
            }
    
    def create_system_prompt(self) -> str:
        """어투 학습을 위한 시스템 프롬프트 생성"""
        sample_size = min(15, len(self.dialogue_samples))
        selected_samples = self.dialogue_samples[:sample_size]
        
        return f"""다음은 특정 캐릭터의 대사입니다:

{chr(10).join(selected_samples)}

위 대사의 말투와 성격을 정확히 따라하여 답변하세요."""

    def extract_knowledge_domains(self) -> List[str]:
        """지식 기반 주제 도메인 생성"""
        # 광범위한 지식 분야들
        knowledge_domains = [
            "과학기술", "역사", "문학", "예술", "철학", "수학", "물리학", "화학", "생물학",
            "지구과학", "천문학", "컴퓨터과학", "의학", "심리학", "사회학", "경제학",
            "정치학", "법학", "교육학", "언어학", "고고학", "인류학", "지리학", "환경과학",
            "건축학", "음악", "미술", "영화", "스포츠", "요리", "여행", "문화"
        ]
        
        # 랜덤하게 8개 선택
        import random
        selected_domains = random.sample(knowledge_domains, min(8, len(knowledge_domains)))
        
        logging.info(f"선택된 지식 도메인: {selected_domains}")
        return selected_domains

    def generate_knowledge_qa_batch(self, batch_size: int = 5, domains: Optional[List[str]] = None) -> List[Dict[str, str]]:
        """지식 기반 질문-답변 쌍 배치 생성 (개선된 어투 반영 버전)"""
        qa_pairs = []
        
        if domains is None:
            domains = self.extract_knowledge_domains()
        
        try:
            actual_batch_size = min(batch_size, 5)
            
            # 대사 샘플 (말투 참조용)
            sample_size = min(10, len(self.dialogue_samples))
            sample_dialogues = self.dialogue_samples[:sample_size]
            
            for i in range(actual_batch_size):
                try:
                    # 지식 도메인 선택
                    domain = domains[i % len(domains)]
                    
                    # 1단계: 해당 분야의 지식 질문 생성
                    question_prompt = f"""1단계: {domain} 분야에서 교육적이고 유익한 지식 질문을 하나만 만드세요.
개인적인 경험이나 감정이 아닌 객관적인 사실이나 개념에 대한 질문이어야 합니다.

질문 생성 예시:
- 과학: "광합성 과정에서 일어나는 화학 반응은 무엇인가요?"
- 역사: "르네상스 시대의 주요 특징은 무엇인가요?"
- 문학: "소설의 3대 요소는 무엇인가요?"

{domain} 분야 질문:"""
                    
                    question = self.generate_text(question_prompt, max_new_tokens=40, temperature=0.7)
                    
                    if not question:
                        continue
                    
                    # 질문 정리
                    question = question.split('\n')[0].strip()
                    if not question.endswith('?'):
                        question += '?'
                    
                    # 2단계: 표준 지식 기반 답변 생성
                    standard_answer_prompt = f"""2단계: 다음 {domain} 분야의 질문에 대해 정확하고 객관적인 지식 정보로 답변하세요.
개인적인 의견이 아닌 사실적이고 교육적인 내용으로만 답변해주세요.

질문: {question}

표준 답변:"""
                    
                    standard_answer = self.generate_text(standard_answer_prompt, max_new_tokens=150, temperature=0.3)
                    
                    if not standard_answer:
                        continue
                    
                    # 3단계: 캐릭터 어투 반영 답변 변환
                    style_conversion_prompt = f"""3단계: 아래 표준 답변을 주어진 캐릭터의 말투와 어투로 자연스럽게 변환하세요.
내용과 정확성은 유지하되, 말하는 방식만 캐릭터의 스타일로 바꿔주세요.

캐릭터 말투 참조:
{chr(10).join(sample_dialogues)}

표준 답변: {standard_answer}

질문: {question}

캐릭터 어투로 변환된 답변:"""
                    
                    styled_answer = self.generate_text(style_conversion_prompt, max_new_tokens=200, temperature=0.6)
                    
                    if styled_answer:
                        # 답변 정리 - 첫 번째 문장이나 의미있는 답변 부분만 추출
                        styled_answer = styled_answer.split('\n')[0].strip()
                        
                        # 질문과 답변이 적절한지 검증
                        if (question and styled_answer and 
                            len(styled_answer) > 15 and 
                            not any(personal_word in question.lower() for personal_word in 
                                   ['나는', '내가', '우리', '당신', '너', '기분', '감정']) and
                            question.endswith('?')):
                            
                            qa_pairs.append({
                                "question": question,
                                "answer": styled_answer,
                                "domain": domain,
                                "standard_answer": standard_answer[:100] + "..." if len(standard_answer) > 100 else standard_answer
                            })
                            
                            logging.info(f"생성 완료 - Q: {question[:50]}... A: {styled_answer[:50]}...")
                    
                    # 메모리 정리
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        
                except Exception as e:
                    logging.warning(f"지식 QA 쌍 {i+1} 생성 실패: {e}")
                    continue
            
            return qa_pairs
            
        except Exception as e:
            logging.error(f"지식 배치 생성 중 오류 발생: {e}")
            return []

    def generate_dataset(self, total_pairs: int = 100, batch_size: int = 5) -> List[Dict[str, str]]:
        """전체 지식 기반 데이터셋 생성"""
        dataset = []
        
        # 허깅페이스 모델은 보통 더 적은 배치 크기 사용
        actual_batch_size = min(batch_size, 5)
        batches_needed = (total_pairs + actual_batch_size - 1) // actual_batch_size
        domains = self.extract_knowledge_domains()
        
        logging.info(f"총 {total_pairs}개의 지식 기반 질문-답변 쌍 생성 시작 (배치 크기: {actual_batch_size})")
        logging.info(f"사용할 지식 도메인: {domains}")
        
        for i in range(batches_needed):
            try:
                # 진행 상황 출력
                current_target = min((i + 1) * actual_batch_size, total_pairs)
                logging.info(f"배치 {i+1}/{batches_needed} 생성 중... (목표: {current_target}개)")
                
                batch = self.generate_knowledge_qa_batch(actual_batch_size, domains)
                
                if batch:
                    dataset.extend(batch)
                    current_count = len(dataset)
                    logging.info(f"진행률: {current_count}/{total_pairs} ({current_count/total_pairs*100:.1f}%) - 이번 배치: {len(batch)}개")
                    
                    # 생성된 도메인 분포 확인
                    if len(dataset) % 20 == 0:  # 20개마다 도메인 분포 출력
                        domain_count = {}
                        for qa in dataset:
                            domain = qa.get('domain', '알 수 없음')
                            domain_count[domain] = domain_count.get(domain, 0) + 1
                        logging.info(f"현재 도메인 분포: {domain_count}")
                else:
                    logging.warning(f"배치 {i+1}에서 지식 QA 쌍 생성 실패")
                
                # 중간 저장 (50개마다)
                if len(dataset) >= 50 and len(dataset) % 50 == 0:
                    self.save_checkpoint(dataset)
                
                # 메모리 정리 및 대기
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                time.sleep(2)  # 모델 과부하 방지를 위해 대기 시간 증가
                
                # 목표 달성 시 종료
                if len(dataset) >= total_pairs:
                    break
                    
            except Exception as e:
                logging.error(f"배치 {i+1} 생성 실패: {e}")
                time.sleep(3)
                continue
        
        # 최종 크기 조정
        dataset = dataset[:total_pairs]
        
        return dataset

    def save_checkpoint(self, dataset: List[Dict[str, str]]):
        """중간 체크포인트 저장"""
        checkpoint_file = f"checkpoint_{self.character_name}_{len(dataset)}.json"
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        logging.info(f"체크포인트 저장: {checkpoint_file}")

    def save_dataset(self, dataset: List[Dict[str, str]], filename: Optional[str] = None):
        """최종 데이터셋 저장"""
        if filename is None:
            filename = f"dialogue_dataset_{self.character_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": {
                    "character_name": self.character_name,
                    "total_pairs": len(dataset),
                    "generated_at": datetime.now().isoformat(),
                    "dialogue_samples_used": len(self.dialogue_samples),
                    "character_traits": self.character_traits,
                    "model_name": self.model_name,
                    "device_used": self.device,
                    "generation_method": "3단계 어투 반영 방식"
                },
                "data": dataset
            }, f, ensure_ascii=False, indent=2)
        
        logging.info(f"데이터셋 저장 완료: {filename} ({len(dataset)}개)")
        return filename

    def validate_dataset(self, dataset: List[Dict[str, str]]) -> Dict[str, any]:
        """데이터셋 품질 검증"""
        if not dataset:
            return {"error": "빈 데이터셋"}
        
        # 기본 통계
        stats = {
            "total": len(dataset),
            "avg_q_length": sum(len(qa["question"]) for qa in dataset) / len(dataset),
            "avg_a_length": sum(len(qa["answer"]) for qa in dataset) / len(dataset),
            "empty_questions": sum(1 for qa in dataset if not qa["question"].strip()),
            "empty_answers": sum(1 for qa in dataset if not qa["answer"].strip()),
            "duplicates": len(dataset) - len(set(qa["question"] for qa in dataset)),
            "model_used": self.model_name
        }
        
        # 도메인 분포 추가
        domain_distribution = {}
        for qa in dataset:
            domain = qa.get('domain', '알 수 없음')
            domain_distribution[domain] = domain_distribution.get(domain, 0) + 1
        
        stats["domain_distribution"] = domain_distribution
        
        # 지식 기반 QA 품질 검증
        personal_questions = 0
        personal_answers = 0
        personal_keywords = ['나는', '내가', '우리', '당신', '너', '기분', '감정', '생각해', '느껴']
        
        for qa in dataset:
            if any(keyword in qa["question"].lower() for keyword in personal_keywords):
                personal_questions += 1
            if any(keyword in qa["answer"].lower() for keyword in personal_keywords):
                personal_answers += 1
        
        stats["personal_questions"] = personal_questions
        stats["personal_answers"] = personal_answers
        stats["knowledge_purity"] = (len(dataset) - personal_questions - personal_answers) / len(dataset) * 100
        
        return stats

def load_dialogues_from_file(filepath: str) -> List[str]:
    """파일에서 대사 로드 (JSON 또는 텍스트 파일 지원)"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            if filepath.endswith('.json'):
                data = json.load(f)
                
                if isinstance(data, list):
                    dialogues = data
                elif isinstance(data, dict):
                    if 'dialogues' in data:
                        dialogues = data['dialogues']
                    elif 'samples' in data:
                        dialogues = data['samples'] 
                    elif 'data' in data:
                        dialogues = data['data']
                    else:
                        for key, value in data.items():
                            if isinstance(value, list):
                                dialogues = value
                                break
                        else:
                            logging.error("JSON 파일에서 대사 리스트를 찾을 수 없습니다.")
                            return []
                else:
                    logging.error("지원하지 않는 JSON 형식입니다.")
                    return []
            else:
                content = f.read()
                if '\n' in content:
                    dialogues = content.strip().split('\n')
                elif '|' in content:
                    dialogues = content.strip().split('|')
                else:
                    dialogues = [content.strip()]
        
        dialogues = [str(d).strip() for d in dialogues if d and str(d).strip()]
        
        logging.info(f"{filepath}에서 {len(dialogues)}개의 대사 로드 완료")
        return dialogues
        
    except json.JSONDecodeError as e:
        logging.error(f"JSON 파일 파싱 실패: {e}")
        return []
    except Exception as e:
        logging.error(f"파일 로드 실패: {e}")
        return []

def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='허깅페이스 모델 기반 지식 질문-답변 데이터셋 생성기 (개선된 어투 반영 버전)')
    parser.add_argument('--dialogues-file', type=str, help='대사가 포함된 텍스트 또는 JSON 파일 경로')
    parser.add_argument('--character-name', type=str, default='캐릭터', help='캐릭터 이름')
    parser.add_argument('--model-name', type=str, default='LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct', 
                       help='허깅페이스 모델 이름 (예: microsoft/DialoGPT-medium, gpt2, skt/kogpt2-base-v2)')
    parser.add_argument('--total-pairs', type=int, default=100, help='생성할 질문-답변 쌍 개수')
    parser.add_argument('--batch-size', type=int, default=5, help='배치 크기')
    parser.add_argument('--output', type=str, help='출력 파일명')
    parser.add_argument('--use-4bit', action='store_true', help='4비트 양자화 사용 (메모리 절약)')
    parser.add_argument('--device', type=str, default='auto', choices=['auto', 'cuda', 'cpu'], help='사용할 디바이스')
    
    args = parser.parse_args()
    
    # GPU 메모리 정보 출력
    if torch.cuda.is_available():
        logging.info(f"CUDA 사용 가능: {torch.cuda.get_device_name()}")
        logging.info(f"GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
    
    # 대사 로드
    if args.dialogues_file:
        dialogue_samples = load_dialogues_from_file(args.dialogues_file)
    else:
        logging.warning("대사 파일이 지정되지 않았습니다. 기본 샘플을 사용합니다.")
        dialogue_samples = [
            "정확한 지식을 바탕으로 설명드리겠습니다.",
            "이 분야에 대해 자세히 알아보시죠.",
            "학문적 관점에서 살펴보면 다음과 같습니다.",
            "연구 결과에 따르면 이러한 사실들이 밝혀졌습니다.",
            "체계적으로 정리해서 말씀드리겠습니다."
        ]
    
    if not dialogue_samples:
        logging.error("대사를 로드할 수 없습니다.")
        return
    
    logging.info(f"로드된 대사 개수: {len(dialogue_samples)}")
    logging.info(f"처음 3개 대사 샘플:\n{chr(10).join(dialogue_samples[:3])}")
    
    try:
        # 생성기 초기화
        generator = HuggingFaceKnowledgeDatasetGenerator(
            dialogue_samples=dialogue_samples,
            character_name=args.character_name,
            model_name=args.model_name,
            use_4bit=args.use_4bit,
            device=args.device
        )
        
        # 데이터셋 생성
        dataset = generator.generate_dataset(
            total_pairs=args.total_pairs, 
            batch_size=args.batch_size
        )
        
        if not dataset:
            logging.error("데이터셋 생성에 실패했습니다.")
            return
        
        # 데이터셋 검증
        stats = generator.validate_dataset(dataset)
        logging.info(f"데이터셋 통계: {stats}")
        
        # 저장
        output_file = generator.save_dataset(dataset, args.output)
        
        # 샘플 출력
        logging.info("\n=== 생성된 샘플 (3단계 어투 반영) ===")
        for i, qa in enumerate(dataset[:3]):
            logging.info(f"\n[{i+1}] 도메인: {qa.get('domain', '알 수 없음')}")
            logging.info(f"Q: {qa['question']}")
            logging.info(f"A: {qa['answer']}")
            if 'standard_answer' in qa:
                logging.info(f"원본 답변: {qa['standard_answer']}")
        
        logging.info(f"\n✅ 어투가 반영된 데이터셋 생성 완료: {output_file}")
        
    except Exception as e:
        logging.error(f"실행 중 오류 발생: {e}")
        return

if __name__ == "__main__":
    main()