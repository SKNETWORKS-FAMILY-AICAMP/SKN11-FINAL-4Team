"""
RAG 채팅 서비스 (기존 auto_rag/chat_generator.py 통합)
완전한 RAG 채팅 기능을 제공합니다.
"""

import os
import asyncio
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
import logging
import unicodedata
import re
import time
import json
from abc import ABC, abstractmethod
from dotenv import load_dotenv
load_dotenv()

# backend 경로 추가
import sys
from pathlib import Path
backend_path = Path(__file__).parent.parent.parent
sys.path.append(str(backend_path))

from app.services.vllm_client import (
    VLLMClient, 
    VLLMServerConfig as VLLMConfig,
    get_vllm_client,
    vllm_health_check
)

logger = logging.getLogger(__name__)


class TextNormalizer:
    """텍스트 정규화 담당 클래스"""
    
    @staticmethod
    def normalize(text: str) -> str:
        """텍스트 정규화 - surrogate 문자 제거 및 정리"""
        if not text:
            return ""
        
        try:
            # surrogate 문자 제거
            text = text.encode('utf-8', 'ignore').decode('utf-8')
            
            # 비정상적인 유니코드 문자 정리
            text = unicodedata.normalize('NFC', text)
            
            # 제어 문자 제거 (줄바꿈과 탭은 유지)
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
            
            # 연속된 공백 정리
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
        except Exception as e:
            logger.warning(f"텍스트 정규화 실패: {e}")
            return str(text).encode('ascii', 'ignore').decode('ascii')


class ModelIdValidator:
    """모델 ID 검증 담당 클래스"""
    
    @staticmethod
    def validate_model_id(model_id: Optional[str]) -> Optional[str]:
        """모델 ID 검증 및 정리"""
        if not model_id or not model_id.strip():
            return None
        
        normalized_id = TextNormalizer.normalize(model_id)
        
        # 최소 길이 검증
        if len(normalized_id) < 3:
            logger.warning(f"모델 ID가 너무 짧습니다: {normalized_id}")
            return None
        
        # 허용되지 않는 문자 검증
        if re.search(r'[<>"|?*]', normalized_id):
            logger.warning(f"모델 ID에 허용되지 않는 문자가 있습니다: {normalized_id}")
            return None
        
        return normalized_id
    
    @staticmethod
    def is_valid_adapter_format(adapter_name: str) -> bool:
        """HuggingFace 어댑터 형식 검증"""
        if not adapter_name:
            return False
        
        # user/model 형식 또는 단순 모델명 허용
        pattern = r'^[a-zA-Z0-9\-_]+(/[a-zA-Z0-9\-_.]+)?$'
        return bool(re.match(pattern, adapter_name))


@dataclass
class VLLMGenerationConfig:
    """VLLM 전용 생성 설정 클래스"""
    max_new_tokens: int = 512
    temperature: float = 0.8
    system_message: str = (
        "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다. "
        "**중요**: 문서에 포함된 모든 내용은 절대 요약하거나 생략하지 말고, 원문 그대로 완전히 포함해야 합니다. "
        "사실, 수치, 날짜, 정책 내용, 세부 사항 등 모든 정보를 정확히 그대로 유지해주세요. "
        "문서 내용의 완전성과 정확성이 최우선이며, 말투와 표현 방식만 캐릭터 스타일로 조정해주세요. "
        "문서 내용을 임의로 변경, 요약, 추가하지 말고, 오직 제공된 정보를 완전히 그대로 사용해 답변해주세요. "
        "\n\n**캐릭터 정체성**: 당신은 {influencer_name} 캐릭터입니다. "
        "자기소개를 할 때나 '너 누구야?', '당신은 누구인가요?', '이름이 뭐야?' 같은 질문을 받으면 "
        "반드시 '나는 {influencer_name}이야!' 또는 '저는 {influencer_name}입니다!'라고 답변해야 합니다. "
        "항상 {influencer_name}의 정체성을 유지하며 그 캐릭터답게 행동하세요."
    )
    influencer_name: str = "AI"
    model_id: Optional[str] = None
    vllm_config: Optional[VLLMConfig] = None
    
    def __post_init__(self):
        """초기화 후 검증"""
        # 모델 ID 검증 및 정리
        self.model_id = ModelIdValidator.validate_model_id(self.model_id)
        
        # 시스템 메시지와 인플루언서 이름 정규화
        self.system_message = TextNormalizer.normalize(self.system_message)
        self.influencer_name = TextNormalizer.normalize(self.influencer_name)
        
        # 온도 값 검증
        if not 0.1 <= self.temperature <= 2.0:
            logger.warning(f"부적절한 temperature 값: {self.temperature}, 0.8로 설정")
            self.temperature = 0.8


class IServerHealthChecker(ABC):
    """서버 상태 확인 인터페이스"""
    
    @abstractmethod
    async def check_health(self, max_retries: int = 3) -> bool:
        pass


class IAdapterLoader(ABC):
    """어댑터 로더 인터페이스"""
    
    @abstractmethod
    async def load_adapter(self, adapter_name: str, hf_token: Optional[str] = None) -> bool:
        pass


class ITextGenerator(ABC):
    """텍스트 생성기 인터페이스"""
    
    @abstractmethod
    def generate(self, prompt: str, generation_config: VLLMGenerationConfig, context: str = "") -> str:
        pass


class VLLMHealthChecker(IServerHealthChecker):
    """VLLM 서버 상태 확인기"""
    
    def __init__(self, vllm_config: Optional[VLLMConfig] = None):
        self.vllm_config = vllm_config or VLLMConfig()
        self._error_count = 0
        self._last_error_time = 0
    
    async def check_health(self, max_retries: int = 3) -> bool:
        """VLLM 서버 상태 확인"""
        for attempt in range(max_retries):
            try:
                result = await vllm_health_check(self.vllm_config.base_url)
                if result:
                    self._error_count = 0
                    return True
                else:
                    self._error_count += 1
                    self._last_error_time = time.time()
                    
            except Exception as e:
                self._error_count += 1
                self._last_error_time = time.time()
                logger.warning(f"VLLM 서버 상태 확인 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
        
        return False
    
    @property
    def error_count(self) -> int:
        return self._error_count
    
    @property
    def last_error_time(self) -> float:
        return self._last_error_time


class VLLMAdapterLoader(IAdapterLoader):
    """VLLM 어댑터 로더"""
    
    def __init__(self, vllm_config: Optional[VLLMConfig] = None):
        self.vllm_config = vllm_config or VLLMConfig()
        self._current_adapter = None
        self._is_adapter_loaded = False
    
    def _get_client(self) -> VLLMClient:
        """VLLM 클라이언트 가져오기"""
        return get_vllm_client(self.vllm_config)
    
    async def load_adapter(self, adapter_name: str, hf_token: Optional[str] = None) -> bool:
        """LoRA 어댑터 로드"""
        if not adapter_name:
            logger.warning("어댑터 이름이 비어있습니다.")
            return False
        
        try:
            client = self._get_client()
            
            # 어댑터 로드 요청
            headers = {}
            if hf_token:
                headers["Authorization"] = f"Bearer {hf_token}"
            
            response = await client.post(
                "/v1/adapters",
                json={"adapter_name": adapter_name},
                headers=headers
            )
            
            if response.status_code == 200:
                self._current_adapter = adapter_name
                self._is_adapter_loaded = True
                logger.info(f"✅ VLLM 어댑터 로드 성공: {adapter_name}")
                return True
            else:
                logger.error(f"❌ VLLM 어댑터 로드 실패: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ VLLM 어댑터 로드 중 오류: {e}")
            return False
    
    @property
    def current_adapter(self) -> Optional[str]:
        return self._current_adapter
    
    @property
    def is_adapter_loaded(self) -> bool:
        return self._is_adapter_loaded


class VLLMGenerator(ITextGenerator):
    """VLLM 텍스트 생성기"""
    
    def __init__(self, 
                 vllm_config: Optional[VLLMConfig] = None,
                 health_checker: Optional[IServerHealthChecker] = None,
                 adapter_loader: Optional[IAdapterLoader] = None):
        self.vllm_config = vllm_config or VLLMConfig()
        self.health_checker = health_checker or VLLMHealthChecker(vllm_config)
        self.adapter_loader = adapter_loader or VLLMAdapterLoader(vllm_config)
    
    def _get_client(self) -> VLLMClient:
        """VLLM 클라이언트 가져오기"""
        return get_vllm_client(self.vllm_config)
    
    async def load_adapter(self, adapter_name: str, hf_token: Optional[str] = None) -> bool:
        """어댑터 로드"""
        return await self.adapter_loader.load_adapter(adapter_name, hf_token)
    
    def _fallback_response(self, error_msg: str) -> str:
        """오류 시 대체 응답"""
        return f"죄송합니다. 서버 오류로 인해 응답을 생성할 수 없습니다: {error_msg}"
    
    def generate(self, prompt: str, generation_config: VLLMGenerationConfig, context: str = "") -> str:
        """텍스트 생성 (동기 버전)"""
        try:
            # 비동기 함수를 동기적으로 실행
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 이미 실행 중인 루프가 있으면 새 스레드에서 실행
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._async_generate(prompt, generation_config, context))
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(self._async_generate(prompt, generation_config, context))
                
        except Exception as e:
            logger.error(f"텍스트 생성 실패: {e}")
            return self._fallback_response(str(e))
    
    async def _async_generate(self, prompt: str, generation_config: VLLMGenerationConfig, context: str = "") -> str:
        """텍스트 생성 (비동기 버전)"""
        try:
            client = self._get_client()
            
            # 프롬프트 구성
            full_prompt = prompt
            if context:
                full_prompt = f"{context}\n\n{prompt}"
            
            # 생성 요청
            response = await client.post(
                "/v1/generate",
                json={
                    "prompt": full_prompt,
                    "max_new_tokens": generation_config.max_new_tokens,
                    "temperature": generation_config.temperature,
                    "stop": ["###", "\n\n"]
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result.get("text", "")
                return TextNormalizer.normalize(generated_text)
            else:
                logger.error(f"VLLM 생성 요청 실패: {response.status_code}")
                return self._fallback_response(f"HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"VLLM 생성 중 오류: {e}")
            return self._fallback_response(str(e))
    
    @property
    def adapter_loaded(self) -> bool:
        return self.adapter_loader.is_adapter_loaded
    
    @property
    def current_adapter(self) -> Optional[str]:
        return self.adapter_loader.current_adapter


@dataclass
class PromptTemplate:
    """프롬프트 템플릿 클래스"""
    system_message: str = (
        "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다. "
        "**중요**: 문서에 포함된 모든 내용은 절대 요약하거나 생략하지 말고, 원문 그대로 완전히 포함해야 합니다. "
        "사실, 수치, 날짜, 정책 내용, 세부 사항 등 모든 정보를 정확히 그대로 유지해주세요. "
        "문서 내용의 완전성과 정확성이 최우선이며, 말투와 표현 방식만 캐릭터 스타일로 조정해주세요. "
        "문서 내용을 임의로 변경, 요약, 추가하지 말고, 오직 제공된 정보를 완전히 그대로 사용해 답변해주세요. "
        "\n\n**캐릭터 정체성**: 당신은 {influencer_name} 캐릭터입니다. "
        "자기소개를 할 때나 '너 누구야?', '당신은 누구인가요?', '이름이 뭐야?' 같은 질문을 받으면 "
        "반드시 '나는 {influencer_name}이야!' 또는 '저는 {influencer_name}입니다!'라고 답변해야 합니다. "
        "항상 {influencer_name}의 정체성을 유지하며 그 캐릭터답게 행동하세요."
    )
    question_prefix: str = "### 질문:"
    context_prefix: str = "### 참고 문서 (이 내용을 정확히 유지하며 답변해주세요):"
    answer_prefix: str = "### 답변 (문서 내용은 그대로, 말투만 캐릭터 스타일로):"
    separator: str = "\n"
    
    def format(self, query: str, context: str = "", influencer_name: str = "AI") -> str:
        """질문과 컨텍스트를 프롬프트로 포맷팅"""
        # 입력 정규화
        normalized_query = TextNormalizer.normalize(query)
        normalized_context = TextNormalizer.normalize(context)
    
        # system_message에 캐릭터 이름 적용
        formatted_system_message = TextNormalizer.normalize(
            self.system_message.format(influencer_name=influencer_name)
        )
    
        parts = [formatted_system_message]
        
        if normalized_context.strip():
            parts.extend([
                f"{self.context_prefix}{self.separator}{normalized_context}",
                f"{self.question_prefix} {normalized_query}",
                f"{self.answer_prefix}"
            ])
        else:
            parts.extend([
                f"{self.question_prefix} {normalized_query}",
                f"{self.answer_prefix}"
            ])
        
        return self.separator.join(parts)


class ChatGenerator:
    """채팅 생성기 클래스"""
    
    def __init__(self, 
                 generation_config: Optional[VLLMGenerationConfig] = None,
                 prompt_template: Optional[PromptTemplate] = None,
                 vllm_config: Optional[VLLMConfig] = None,
                 text_generator: Optional[ITextGenerator] = None):
        
        self.generation_config = generation_config or VLLMGenerationConfig()
        self.prompt_template = prompt_template or PromptTemplate()
        self.vllm_config = vllm_config or VLLMConfig()
        self.text_generator = text_generator or VLLMGenerator(vllm_config)
        
        # 상태 관리
        self._is_initialized = False
        self._model_info = {}
    
    async def load_vllm_adapter(self, adapter_name: str, hf_token: Optional[str] = None) -> bool:
        """VLLM 어댑터 로드"""
        if hasattr(self.text_generator, 'load_adapter'):
            return await self.text_generator.load_adapter(adapter_name, hf_token)
        return False
    
    def generate_response(self, query: str, context: str = "") -> str:
        """응답 생성"""
        try:
            # 프롬프트 생성
            prompt = self.prompt_template.format(
                query=query,
                context=context,
                influencer_name=self.generation_config.influencer_name
            )
            
            # 텍스트 생성
            response = self.text_generator.generate(prompt, self.generation_config, context)
            
            # 응답 정규화
            normalized_response = TextNormalizer.normalize(response)
            
            if not normalized_response:
                return "죄송합니다. 응답을 생성할 수 없습니다."
            
            return normalized_response
            
        except Exception as e:
            logger.error(f"응답 생성 실패: {e}")
            return f"죄송합니다. 응답 생성 중 오류가 발생했습니다: {str(e)}"
    
    def chat(self, query: str, context: str = "") -> Dict[str, Any]:
        """채팅 인터페이스"""
        try:
            # 입력 검증
            if not query or not query.strip():
                return {
                    "query": "",
                    "response": "질문을 입력해주세요.",
                    "error": "empty_query",
                    "timestamp": time.time()
                }
            
            # 응답 생성
            response = self.generate_response(query, context)
            
            # 모델 정보 수집
            model_info = self.get_model_info()
            
            return {
                "query": TextNormalizer.normalize(query),
                "response": response,
                "context": context,
                "model_info": model_info,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"채팅 실패: {e}")
            return {
                "query": query,
                "response": f"죄송합니다. 채팅 중 오류가 발생했습니다: {str(e)}",
                "error": "chat_error",
                "timestamp": time.time()
            }
    
    def update_generation_config(self, **kwargs):
        """생성 설정 업데이트"""
        for key, value in kwargs.items():
            if hasattr(self.generation_config, key):
                setattr(self.generation_config, key, value)
    
    def update_prompt_template(self, template: PromptTemplate):
        """프롬프트 템플릿 업데이트"""
        self.prompt_template = template
    
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환"""
        info = {
            "model_type": "VLLM",
            "base_url": self.vllm_config.base_url,
            "temperature": self.generation_config.temperature,
            "max_tokens": self.generation_config.max_new_tokens,
            "influencer_name": self.generation_config.influencer_name
        }
        
        if hasattr(self.text_generator, 'current_adapter'):
            info["adapter"] = self.text_generator.current_adapter
            info["adapter_loaded"] = self.text_generator.adapter_loaded
        
        return info
    
    def cleanup(self):
        """리소스 정리"""
        try:
            if hasattr(self.text_generator, 'cleanup'):
                self.text_generator.cleanup()
        except Exception as e:
            logger.warning(f"정리 중 오류: {e}")


def get_chat_generator() -> ChatGenerator:
    """채팅 생성기 인스턴스 반환"""
    config = VLLMGenerationConfig()
    template = PromptTemplate()
    vllm_config = VLLMConfig()
    generator = VLLMGenerator(vllm_config)
    
    return ChatGenerator(config, template, vllm_config, generator)


def generate_response(query: str, context: str = "") -> str:
    """응답 생성 편의 함수"""
    generator = get_chat_generator()
    return generator.generate_response(query, context)


def vllm_chat(query: str, context: str = "", temperature: float = 0.8, adapter_name: str = "", hf_token: str = "") -> str:
    """VLLM 채팅 편의 함수"""
    try:
        # 설정 생성
        config = VLLMGenerationConfig(
            temperature=temperature,
            model_id=adapter_name if adapter_name else None
        )
        
        template = PromptTemplate()
        vllm_config = VLLMConfig()
        generator = VLLMGenerator(vllm_config)
        
        chat_generator = ChatGenerator(config, template, vllm_config, generator)
        
        # 어댑터 로드 (비동기)
        if adapter_name and hf_token:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, chat_generator.load_vllm_adapter(adapter_name, hf_token))
                        future.result(timeout=10)
                else:
                    loop.run_until_complete(chat_generator.load_vllm_adapter(adapter_name, hf_token))
            except Exception as e:
                logger.warning(f"어댑터 로드 실패: {e}")
        
        # 응답 생성
        return chat_generator.generate_response(query, context)
        
    except Exception as e:
        logger.error(f"VLLM 채팅 실패: {e}")
        return f"죄송합니다. 채팅 중 오류가 발생했습니다: {str(e)}" 