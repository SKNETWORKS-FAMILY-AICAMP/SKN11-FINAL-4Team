# -*- coding: utf-8 -*-
import json
import time
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


class Gender(Enum):
    MALE = "남성"
    FEMALE = "여성"
    NON_BINARY = "중성"


class ToneVariation(Enum):
    FORMAL = "격식적"
    FRIENDLY = "친근한"
    CASUAL = "캐주얼"


@dataclass
class ToneInfo:
    """어조 정보를 담는 클래스"""
    variation: ToneVariation
    description: str
    intensity: str  # "높음", "보통", "낮음"
    formality_level: str  # "매우 격식적", "격식적", "보통", "친근한", "매우 친근한"


@dataclass
class CharacterProfile:
    name: str
    description: str
    age: int
    gender: Gender
    personality: str
    mbti: str
    
    def __post_init__(self):
        """MBTI 유효성 검사"""
        valid_mbti = {
            'INTJ', 'INTP', 'ENTJ', 'ENTP',
            'INFJ', 'INFP', 'ENFJ', 'ENFP',
            'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
            'ISTP', 'ISFP', 'ESTP', 'ESFP'
        }
        if self.mbti.upper() not in valid_mbti:
            raise ValueError(f"올바르지 않은 MBTI 타입: {self.mbti}")
        self.mbti = self.mbti.upper()


class SpeechGenerator:
    def __init__(self, api_key: Optional[str] = None):
        """
        OpenAI Batch API를 사용한 캐릭터 기반 어투 생성기
        
        Args:
            api_key: OpenAI API 키 (환경변수 OPENAI_API_KEY로도 설정 가능)
        """
        self.client = OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
        
        # MBTI별 특징 정의
        self.mbti_traits = {
            'INTJ': {
                'speech_style': '논리적이고 간결한 표현을 선호하며, 체계적으로 말합니다.',
                'characteristics': '독립적, 전략적 사고, 미래 지향적, 완벽주의 성향'
            },
            'INTP': {
                'speech_style': '분석적이고 신중한 표현을 사용하며, 가능성을 탐구하는 말투입니다.',
                'characteristics': '호기심 많음, 논리적 분석, 독창적 아이디어, 유연한 사고'
            },
            'ENTJ': {
                'speech_style': '자신감 있고 단호한 표현을 사용하며, 리더십을 보여주는 말투입니다.',
                'characteristics': '지도력, 목표 지향적, 결단력, 효율성 추구'
            },
            'ENTP': {
                'speech_style': '창의적이고 활발한 표현을 사용하며, 새로운 아이디어를 제시하는 말투입니다.',
                'characteristics': '창의적, 적응력, 열정적, 토론을 즐김'
            },
            'INFJ': {
                'speech_style': '따뜻하고 통찰력 있는 표현을 사용하며, 깊이 있는 대화를 선호합니다.',
                'characteristics': '직관적, 이상주의적, 공감능력, 미래 비전'
            },
            'INFP': {
                'speech_style': '진실하고 개인적인 표현을 사용하며, 가치관을 중시하는 말투입니다.',
                'characteristics': '개인적 가치 중시, 창의성, 공감적, 개방적'
            },
            'ENFJ': {
                'speech_style': '격려적이고 협력적인 표현을 사용하며, 다른 사람을 도우려는 말투입니다.',
                'characteristics': '타인 지향적, 카리스마, 협력적, 영감을 주는'
            },
            'ENFP': {
                'speech_style': '열정적이고 긍정적인 표현을 사용하며, 가능성을 탐구하는 말투입니다.',
                'characteristics': '열정적, 사교적, 창의적, 자유로운 영혼'
            },
            'ISTJ': {
                'speech_style': '신중하고 체계적인 표현을 사용하며, 사실에 기반한 말투입니다.',
                'characteristics': '책임감, 신뢰성, 체계적, 전통 중시'
            },
            'ISFJ': {
                'speech_style': '배려깊고 조심스러운 표현을 사용하며, 다른 사람을 생각하는 말투입니다.',
                'characteristics': '배려심, 협력적, 실용적, 안정성 추구'
            },
            'ESTJ': {
                'speech_style': '직접적이고 체계적인 표현을 사용하며, 효율성을 강조하는 말투입니다.',
                'characteristics': '조직력, 현실적, 책임감, 전통적 가치'
            },
            'ESFJ': {
                'speech_style': '친근하고 협력적인 표현을 사용하며, 조화를 중시하는 말투입니다.',
                'characteristics': '사교적, 협력적, 배려심, 조화 추구'
            },
            'ISTP': {
                'speech_style': '간결하고 실용적인 표현을 사용하며, 필요한 말만 하는 말투입니다.',
                'characteristics': '실용적, 독립적, 적응력, 문제 해결 능력'
            },
            'ISFP': {
                'speech_style': '부드럽고 개인적인 표현을 사용하며, 감정을 소중히 하는 말투입니다.',
                'characteristics': '예술적, 유연성, 개인적 가치, 평화로움'
            },
            'ESTP': {
                'speech_style': '활발하고 즉흥적인 표현을 사용하며, 현재에 집중하는 말투입니다.',
                'characteristics': '활동적, 현실적, 사교적, 즉흥적'
            },
            'ESFP': {
                'speech_style': '따뜻하고 표현력이 풍부한 말투를 사용하며, 긍정적인 에너지를 전달합니다.',
                'characteristics': '사교적, 따뜻함, 즉흥적, 긍정적'
            }
        }

    def get_tone_variations(self) -> Dict[ToneVariation, ToneInfo]:
        """3가지 어조 변형 정보를 반환합니다."""
        return {
            ToneVariation.FORMAL: ToneInfo(
                variation=ToneVariation.FORMAL,
                description="정중하고 예의바른 격식적인 어조",
                intensity="높음",
                formality_level="매우 격식적"
            ),
            ToneVariation.FRIENDLY: ToneInfo(
                variation=ToneVariation.FRIENDLY,
                description="따뜻하고 친근한 어조",
                intensity="보통",
                formality_level="친근한"
            ),
            ToneVariation.CASUAL: ToneInfo(
                variation=ToneVariation.CASUAL,
                description="화가 나는 친구의 어조",
                intensity="높음",
                formality_level="매우 분노적"
            )
        }
    
    def create_character_prompt_with_tone(self, character: CharacterProfile, tone_info: ToneInfo) -> str:
        """
        캐릭터 정보와 어조 정보를 바탕으로 시스템 프롬프트를 생성합니다.
        
        Args:
            character: 캐릭터 프로필
            tone_info: 어조 정보
            
        Returns:
            생성된 시스템 프롬프트
        """
        mbti_info = self.mbti_traits.get(character.mbti, {})
        
        # 어조별 추가 지침
        tone_instructions = {
            ToneVariation.FORMAL: "높임말을 사용하고, 정중하며 공손한 표현을 사용해주세요. 업무나 공식적인 상황에 적합한 문체로 답변하세요.",
            ToneVariation.FRIENDLY: "친구와 대화하듯 따뜻하고 친근한 말투를 사용해주세요. 적절한 존댓말을 사용하되 친밀감을 표현하세요.",
            ToneVariation.CASUAL: "편안하고 자연스러운 일상 대화체를 사용해주세요. 상황에 따라 반말도 적절히 사용하되 무례하지 않게 하세요."
        }
        
        prompt = f"""당신은 다음과 같은 캐릭터로 답변해주세요:

캐릭터 정보:
- 이름: {character.name}
- 설명: {character.description}
- 나이: {character.age}세
- 성별: {character.gender.value}
- 성격: {character.personality}
- MBTI: {character.mbti}
- MBTI 특징: {mbti_info.get('characteristics', '정보 없음')}
- 기본 말투 특성: {mbti_info.get('speech_style', '일반적인 말투')}

어조 설정:
- 어조 유형: {tone_info.variation.value}
- 어조 설명: {tone_info.description}
- 격식 수준: {tone_info.formality_level}
- 강도: {tone_info.intensity}

답변 시 주의사항:
1. 위 캐릭터의 성격과 MBTI 특성을 반영하여 답변하세요.
2. {tone_instructions[tone_info.variation]}
3. 해당 캐릭터가 {tone_info.variation.value} 어조로 실제로 말하는 것처럼 자연스럽게 답변하세요.
4. 캐릭터의 개성과 특징이 드러나도록 답변하세요.
5. 일관된 캐릭터와 어조를 유지하며 답변하세요.
6. 나이와 성별에 맞는 적절한 언어 사용을 해주세요."""
        
        return prompt

    def create_character_prompt(self, character: CharacterProfile) -> str:
        """
        캐릭터 정보를 바탕으로 기본 시스템 프롬프트를 생성합니다. (하위 호환성)
        
        Args:
            character: 캐릭터 프로필
            
        Returns:
            생성된 시스템 프롬프트
        """
        # 기본적으로 친근한 어조 사용
        tone_info = self.get_tone_variations()[ToneVariation.FRIENDLY]
        return self.create_character_prompt_with_tone(character, tone_info)
    
    def create_batch_requests_for_character_tones(self, user_messages: List[str], character: CharacterProfile) -> List[Dict[str, Any]]:
        """
        하나의 캐릭터에 대해 3가지 어조로 배치 요청을 생성합니다.
        
        Args:
            user_messages: 변환할 사용자 메시지 리스트
            character: 캐릭터 프로필
            
        Returns:
            배치 요청 객체 리스트
        """
        requests = []
        tone_variations = self.get_tone_variations()
        
        for i, message in enumerate(user_messages):
            for tone_variation, tone_info in tone_variations.items():
                system_prompt = self.create_character_prompt_with_tone(character, tone_info)
                request = {
                    "custom_id": f"msg_{i}_tone_{tone_variation.name}_{character.name}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": message}
                        ],
                        "max_tokens": 1000,
                        "temperature": 0.8
                    }
                }
                requests.append(request)
        
        return requests

    def create_batch_requests_for_characters(self, user_messages: List[str], characters: List[CharacterProfile]) -> List[Dict[str, Any]]:
        """
        캐릭터별 배치 요청을 위한 요청 객체들을 생성합니다.
        
        Args:
            user_messages: 변환할 사용자 메시지 리스트
            characters: 캐릭터 프로필 리스트
            
        Returns:
            배치 요청 객체 리스트
        """
        requests = []
        
        for i, message in enumerate(user_messages):
            for j, character in enumerate(characters):
                system_prompt = self.create_character_prompt(character)
                request = {
                    "custom_id": f"msg_{i}_char_{j}_{character.name}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": message}
                        ],
                        "max_tokens": 1000,
                        "temperature": 0.8
                    }
                }
                requests.append(request)
        
        return requests

    def create_batch_requests(self, user_messages: List[str]) -> List[Dict[str, Any]]:
        """
        기본 어투별 배치 요청을 위한 요청 객체들을 생성합니다. (하위 호환성)
        
        Args:
            user_messages: 변환할 사용자 메시지 리스트
            
        Returns:
            배치 요청 객체 리스트
        """
        # 기본 캐릭터들 생성
        default_characters = [
            CharacterProfile(
                name="격식있는_직장인",
                description="전문적이고 격식있는 비즈니스 상황에 적합한 캐릭터",
                age=35,
                gender=Gender.NON_BINARY,
                personality="신중하고 예의바르며 전문적인 성격",
                mbti="ISTJ"
            ),
            CharacterProfile(
                name="친근한_친구",
                description="따뜻하고 친근한 일상 대화에 적합한 캐릭터",
                age=25,
                gender=Gender.NON_BINARY,
                personality="밝고 친근하며 공감능력이 뛰어난 성격",
                mbti="ENFP"
            ),
            CharacterProfile(
                name="화난 친구",
                description="편안하고 자연스러운 대화에 적합한 캐릭터",
                age=22,
                gender=Gender.NON_BINARY,
                personality="자유롭고 솔직하며 유머러스한 성격",
                mbti="ESTP"
            )
        ]
        
        return self.create_batch_requests_for_characters(user_messages, default_characters)

    def create_batch_file(self, requests: List[Dict[str, Any]], filename: str = None) -> str:
        """
        배치 요청을 JSONL 파일로 저장합니다.
        
        Args:
            requests: 배치 요청 객체 리스트
            filename: 저장할 파일명 (기본값: timestamp 사용)
            
        Returns:
            생성된 파일 경로
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"batch_requests_{timestamp}.jsonl"
        
        with open(filename, 'w', encoding='utf-8') as f:
            for request in requests:
                f.write(json.dumps(request, ensure_ascii=False) + '\n')
        
        return filename

    def upload_batch_file(self, file_path: str) -> str:
        """
        배치 파일을 OpenAI에 업로드합니다.
        
        Args:
            file_path: 업로드할 파일 경로
            
        Returns:
            업로드된 파일의 ID
        """
        with open(file_path, 'rb') as f:
            batch_input_file = self.client.files.create(
                file=f,
                purpose="batch"
            )
        
        return batch_input_file.id

    def create_batch(self, input_file_id: str, description: str = "Speech tone generation batch") -> str:
        """
        배치 작업을 생성합니다.
        
        Args:
            input_file_id: 입력 파일 ID
            description: 배치 설명
            
        Returns:
            배치 ID
        """
        batch = self.client.batches.create(
            input_file_id=input_file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"description": description}
        )
        
        return batch.id

    def check_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """
        배치 작업 상태를 확인합니다.
        
        Args:
            batch_id: 배치 ID
            
        Returns:
            배치 상태 정보
        """
        batch = self.client.batches.retrieve(batch_id)
        return {
            "id": batch.id,
            "status": batch.status,
            "created_at": batch.created_at,
            "completed_at": batch.completed_at,
            "failed_at": batch.failed_at,
            "request_counts": batch.request_counts.__dict__ if batch.request_counts else None
        }

    def download_batch_results(self, batch_id: str, output_file: str = None) -> str:
        """
        완료된 배치 결과를 다운로드합니다.
        
        Args:
            batch_id: 배치 ID
            output_file: 결과를 저장할 파일명
            
        Returns:
            다운로드된 파일 경로
        """
        batch = self.client.batches.retrieve(batch_id)
        
        if batch.status != "completed":
            raise ValueError(f"Batch is not completed. Current status: {batch.status}")
        
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"batch_results_{timestamp}.jsonl"
        
        result_file_id = batch.output_file_id
        result = self.client.files.content(result_file_id)
        
        with open(output_file, 'wb') as f:
            f.write(result.content)
        
        return output_file

    def parse_batch_results_with_tone_info(self, results_file: str, character: CharacterProfile) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        배치 결과 파일을 파싱하여 메시지별, 어조별로 정리하고 어조 정보도 함께 반환합니다.
        
        Args:
            results_file: 결과 파일 경로
            character: 캐릭터 프로필
            
        Returns:
            {message_index: {tone_name: {"text": generated_text, "tone_info": ToneInfo}}} 형태의 딕셔너리
        """
        results = {}
        tone_variations = self.get_tone_variations()
        
        with open(results_file, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                custom_id = data['custom_id']
                
                # custom_id 파싱: msg_{i}_tone_{TONE_NAME}_{character_name}
                parts = custom_id.split('_')
                msg_idx = int(parts[1])
                
                if 'tone' in custom_id:
                    # 새로운 어조 기반 형식
                    tone_name = parts[3]  # FORMAL, FRIENDLY, CASUAL
                    try:
                        tone_variation = ToneVariation[tone_name]
                        tone_info = tone_variations[tone_variation]
                        key = tone_variation.value  # "격식적", "친근한", "캐주얼"
                    except KeyError:
                        # 알 수 없는 어조인 경우
                        key = tone_name
                        tone_info = None
                else:
                    # 기존 형식 처리 (하위 호환성)
                    key = parts[2] if len(parts) > 2 else "unknown"
                    tone_info = None
                
                if msg_idx not in results:
                    results[msg_idx] = {}
                
                # 응답에서 텍스트 추출
                if data.get('response') and data['response'].get('body'):
                    content = data['response']['body']['choices'][0]['message']['content']
                    results[msg_idx][key] = {
                        "text": content,
                        "tone_info": {
                            "variation": tone_info.variation.value if tone_info else key,
                            "description": tone_info.description if tone_info else "설명 없음",
                            "intensity": tone_info.intensity if tone_info else "보통",
                            "formality_level": tone_info.formality_level if tone_info else "보통"
                        } if tone_info else None,
                        "character_info": {
                            "name": character.name,
                            "age": character.age,
                            "gender": character.gender.value,
                            "personality": character.personality,
                            "mbti": character.mbti
                        }
                    }
                else:
                    results[msg_idx][key] = {
                        "text": "Error: No response generated",
                        "tone_info": None,
                        "character_info": {
                            "name": character.name,
                            "age": character.age,
                            "gender": character.gender.value,
                            "personality": character.personality,
                            "mbti": character.mbti
                        }
                    }
        
        return results

    def parse_batch_results(self, results_file: str) -> Dict[str, Dict[str, str]]:
        """
        배치 결과 파일을 파싱하여 메시지별, 캐릭터별로 정리합니다. (하위 호환성)
        
        Args:
            results_file: 결과 파일 경로
            
        Returns:
            {message_index: {character_name: generated_text}} 형태의 딕셔너리
        """
        results = {}
        
        with open(results_file, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                custom_id = data['custom_id']
                
                # custom_id 파싱: msg_{i}_char_{j}_{character_name} 또는 msg_{i}_{tone}
                parts = custom_id.split('_')
                msg_idx = int(parts[1])
                
                if 'tone' in custom_id:
                    # 새로운 어조 기반 형식
                    tone_name = parts[3]
                    try:
                        tone_variation = ToneVariation[tone_name]
                        key = tone_variation.value
                    except KeyError:
                        key = tone_name
                elif 'char' in custom_id:
                    # 캐릭터 기반 형식
                    character_name = '_'.join(parts[4:])  # 캐릭터 이름 (언더스코어 포함 가능)
                    key = character_name
                else:
                    # 기존 어투 기반 형식 (하위 호환성)
                    key = parts[2]
                
                if msg_idx not in results:
                    results[msg_idx] = {}
                
                # 응답에서 텍스트 추출
                if data.get('response') and data['response'].get('body'):
                    content = data['response']['body']['choices'][0]['message']['content']
                    results[msg_idx][key] = content
                else:
                    results[msg_idx][key] = "Error: No response generated"
        
        return results

    def generate_character_tone_variations(self, messages: List[str], character: CharacterProfile, wait_for_completion: bool = True) -> Dict[str, Any]:
        """
        하나의 캐릭터에 대해 3가지 어조로 변환된 텍스트를 생성합니다.
        
        Args:
            messages: 변환할 메시지 리스트
            character: 캐릭터 프로필
            wait_for_completion: 완료까지 대기할지 여부
            
        Returns:
            배치 ID 또는 완료된 결과 (어조 정보 포함)
        """
        print(f"처리할 메시지 수: {len(messages)}")
        print(f"캐릭터: {character.name} ({character.mbti})")
        
        # 1. 배치 요청 생성
        requests = self.create_batch_requests_for_character_tones(messages, character)
        print(f"생성된 요청 수: {len(requests)} (3가지 어조)")
        
        # 2. 배치 파일 생성
        batch_file = self.create_batch_file(requests)
        print(f"배치 파일 생성: {batch_file}")
        
        # 3. 파일 업로드
        file_id = self.upload_batch_file(batch_file)
        print(f"파일 업로드 완료: {file_id}")
        
        # 4. 배치 작업 생성
        batch_id = self.create_batch(file_id, f"Character tone variations - {character.name}")
        print(f"배치 작업 생성: {batch_id}")
        
        if not wait_for_completion:
            return {
                "batch_id": batch_id, 
                "status": "submitted", 
                "character": character.name,
                "tone_variations": [tone.value for tone in self.get_tone_variations().keys()]
            }
        
        # 5. 완료 대기
        print("배치 처리 대기 중...")
        while True:
            status = self.check_batch_status(batch_id)
            print(f"현재 상태: {status['status']}")
            
            if status['status'] == 'completed':
                break
            elif status['status'] == 'failed':
                raise Exception("배치 처리 실패")
            
            time.sleep(30)  # 30초마다 상태 확인
        
        # 6. 결과 다운로드
        results_file = self.download_batch_results(batch_id)
        print(f"결과 파일 다운로드: {results_file}")
        
        # 7. 결과 파싱 (어조 정보 포함)
        parsed_results = self.parse_batch_results_with_tone_info(results_file, character)
        
        return {
            "batch_id": batch_id,
            "status": "completed",
            "results_file": results_file,
            "results": parsed_results,
            "character": character.name,
            "tone_variations": [tone.value for tone in self.get_tone_variations().keys()]
        }

    def get_async_results_with_tone_info(self, batch_id: str, character: CharacterProfile) -> Dict[str, Any]:
        """
        비동기로 제출된 배치의 결과를 어조 정보와 함께 가져옵니다.
        
        Args:
            batch_id: 배치 ID
            character: 캐릭터 프로필
            
        Returns:
            배치 결과 또는 상태 정보 (어조 정보 포함)
        """
        status = self.check_batch_status(batch_id)
        
        if status['status'] == 'completed':
            # 결과 다운로드 및 파싱
            results_file = self.download_batch_results(batch_id)
            parsed_results = self.parse_batch_results_with_tone_info(results_file, character)
            
            return {
                "batch_id": batch_id,
                "status": "completed",
                "results_file": results_file,
                "results": parsed_results,
                "character": character.name,
                "tone_variations": [tone.value for tone in self.get_tone_variations().keys()]
            }
        else:
            return {
                "batch_id": batch_id,
                "status": status['status'],
                "message": f"배치가 아직 완료되지 않았습니다. 현재 상태: {status['status']}",
                "character": character.name
            }

    def generate_character_speeches(self, messages: List[str], characters: List[CharacterProfile], wait_for_completion: bool = True) -> Dict[str, Any]:
        """
        메시지들에 대해 지정된 캐릭터들의 어투로 변환된 텍스트를 생성합니다.
        
        Args:
            messages: 변환할 메시지 리스트
            characters: 캐릭터 프로필 리스트
            wait_for_completion: 완료까지 대기할지 여부
            
        Returns:
            배치 ID 또는 완료된 결과
        """
        print(f"처리할 메시지 수: {len(messages)}")
        print(f"캐릭터 수: {len(characters)}")
        
        # 1. 배치 요청 생성
        requests = self.create_batch_requests_for_characters(messages, characters)
        print(f"생성된 요청 수: {len(requests)}")
        
        # 2. 배치 파일 생성
        batch_file = self.create_batch_file(requests)
        print(f"배치 파일 생성: {batch_file}")
        
        # 3. 파일 업로드
        file_id = self.upload_batch_file(batch_file)
        print(f"파일 업로드 완료: {file_id}")
        
        # 4. 배치 작업 생성
        batch_id = self.create_batch(file_id, f"Character speech generation batch - {len(characters)} characters")
        print(f"배치 작업 생성: {batch_id}")
        
        if not wait_for_completion:
            return {"batch_id": batch_id, "status": "submitted", "characters": [c.name for c in characters]}
        
        # 5. 완료 대기
        print("배치 처리 대기 중...")
        while True:
            status = self.check_batch_status(batch_id)
            print(f"현재 상태: {status['status']}")
            
            if status['status'] == 'completed':
                break
            elif status['status'] == 'failed':
                raise Exception("배치 처리 실패")
            
            time.sleep(30)  # 30초마다 상태 확인
        
        # 6. 결과 다운로드
        results_file = self.download_batch_results(batch_id)
        print(f"결과 파일 다운로드: {results_file}")
        
        # 7. 결과 파싱
        parsed_results = self.parse_batch_results(results_file)
        
        return {
            "batch_id": batch_id,
            "status": "completed",
            "results_file": results_file,
            "results": parsed_results,
            "characters": [c.name for c in characters]
        }

    def generate_speech_tones(self, messages: List[str], wait_for_completion: bool = True) -> Dict[str, Any]:
        """
        메시지들에 대해 기본 3가지 어투로 변환된 텍스트를 생성합니다. (하위 호환성)
        
        Args:
            messages: 변환할 메시지 리스트
            wait_for_completion: 완료까지 대기할지 여부
            
        Returns:
            배치 ID 또는 완료된 결과
        """
        print(f"처리할 메시지 수: {len(messages)}")
        
        # 1. 배치 요청 생성 (기본 캐릭터 사용)
        requests = self.create_batch_requests(messages)
        print(f"생성된 요청 수: {len(requests)}")
        
        # 2. 배치 파일 생성
        batch_file = self.create_batch_file(requests)
        print(f"배치 파일 생성: {batch_file}")
        
        # 3. 파일 업로드
        file_id = self.upload_batch_file(batch_file)
        print(f"파일 업로드 완료: {file_id}")
        
        # 4. 배치 작업 생성
        batch_id = self.create_batch(file_id)
        print(f"배치 작업 생성: {batch_id}")
        
        if not wait_for_completion:
            return {"batch_id": batch_id, "status": "submitted"}
        
        # 5. 완료 대기
        print("배치 처리 대기 중...")
        while True:
            status = self.check_batch_status(batch_id)
            print(f"현재 상태: {status['status']}")
            
            if status['status'] == 'completed':
                break
            elif status['status'] == 'failed':
                raise Exception("배치 처리 실패")
            
            time.sleep(30)  # 30초마다 상태 확인
        
        # 6. 결과 다운로드
        results_file = self.download_batch_results(batch_id)
        print(f"결과 파일 다운로드: {results_file}")
        
        # 7. 결과 파싱
        parsed_results = self.parse_batch_results(results_file)
        
        return {
            "batch_id": batch_id,
            "status": "completed",
            "results_file": results_file,
            "results": parsed_results
        }

    def get_async_results(self, batch_id: str) -> Dict[str, Any]:
        """
        비동기로 제출된 배치의 결과를 가져옵니다.
        
        Args:
            batch_id: 배치 ID
            
        Returns:
            배치 결과 또는 상태 정보
        """
        status = self.check_batch_status(batch_id)
        
        if status['status'] == 'completed':
            # 결과 다운로드 및 파싱
            results_file = self.download_batch_results(batch_id)
            parsed_results = self.parse_batch_results(results_file)
            
            return {
                "batch_id": batch_id,
                "status": "completed",
                "results_file": results_file,
                "results": parsed_results
            }
        else:
            return {
                "batch_id": batch_id,
                "status": status['status'],
                "message": f"배치가 아직 완료되지 않았습니다. 현재 상태: {status['status']}"
            }


def main():
    """사용 예시"""
    generator = SpeechGenerator()
    
    # 테스트 메시지들
    test_messages = [
        "안녕하세요! 오늘 날씨가 정말 좋네요.",
        "회의가 내일 오후 2시로 연기되었습니다.",
        "이 프로젝트에 대해 어떻게 생각하시나요?"
    ]
    
    # 테스트용 캐릭터 정의
    test_character = CharacterProfile(
        name="두퍼츠먼츠",
        description="자칭 \"사악한 과학자\"로, 항상 말도 안 되는 장치를 만들어 세계 지배를 꿈꾸는 인물. 하지만 번번이 실패하고, 숙적인 오리너구리 페리에게 저지당한다. 어린 시절의 트라우마로 인해 엉뚱하면서도 짠한 사연을 자주 털어놓으며, 의외로 정 많고 인간적인 면도 있다.",
        age="40대~50대",
        gender=Gender.MALE,
        personality="감정 기복이 심하고 다소 유치하지만 창의적이며, 자기 연민이 강하고 가족애도 깊은 편. 과학자답게 발명에는 진심이지만 계획은 늘 어설프다.",
        mbti="ENTP"
    )
    
    try:
        print("=== OpenAI Batch API 캐릭터 어조 변형 생성 테스트 ===")
        
        # 1. 하나의 캐릭터로 3가지 어조 생성 (새로운 기능)
        print(f"\n1. '{test_character.name}' 캐릭터의 3가지 어조 변형 생성 (비동기):")
        tone_result = generator.generate_character_tone_variations(
            test_messages, 
            test_character, 
            wait_for_completion=False
        )
        print(f"배치 ID: {tone_result['batch_id']}")
        print(f"캐릭터: {tone_result['character']}")
        print(f"어조 변형: {tone_result['tone_variations']}")
        
        # 2. 상태 확인
        print("\n2. 배치 상태 확인:")
        status_result = generator.get_async_results_with_tone_info(tone_result['batch_id'], test_character)
        print(f"상태: {status_result['status']}")
        
        # 3. 기존 호환성 테스트
        print("\n3. 기존 방식 테스트 (하위 호환성):")
        basic_result = generator.generate_speech_tones(test_messages, wait_for_completion=False)
        print(f"배치 ID: {basic_result['batch_id']}")
        
        # 동기 방식 테스트 (완료까지 대기) - 실제 테스트용으로 주석 처리
        print("\n4. 동기 방식으로 처리 (완료까지 대기):")
        result = generator.generate_character_tone_variations(test_messages, test_character, wait_for_completion=True)
        
        # 결과 출력
        for msg_idx, tones in result['results'].items():
            print(f"\n원본 메시지 {msg_idx}: {test_messages[msg_idx]}")
            print("-" * 80)
            for tone_name, tone_data in tones.items():
                print(f"[{tone_name}]:")
                print(f"텍스트: {tone_data['text']}")
                if tone_data['tone_info']:
                    print(f"어조 설명: {tone_data['tone_info']['description']}")
                    print(f"격식 수준: {tone_data['tone_info']['formality_level']}")
                print("-" * 40)
    
    except Exception as e:
        print(f"오류 발생: {e}")


if __name__ == "__main__":
    main()