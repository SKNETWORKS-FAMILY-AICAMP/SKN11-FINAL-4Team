"""
프롬프트 최적화 서비스
사용자 입력 프롬프트를 ComfyUI에 최적화된 영문 프롬프트로 변환
"""

import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger(__name__)

# OpenAI 클라이언트 초기화
openai_client = None
if settings.OPENAI_API_KEY:
    try:
        import openai
        openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("OpenAI client initialized for prompt optimization")
    except ImportError:
        logger.warning("OpenAI package not installed. Using mock optimization.")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")


class PromptOptimizationRequest(BaseModel):
    """프롬프트 최적화 요청"""
    original_prompt: str  # 사용자 입력 (한글/영문)
    style: str = "realistic"  # realistic, anime, artistic, photograph
    quality_level: str = "high"  # low, medium, high, ultra
    aspect_ratio: str = "1:1"  # 1:1, 16:9, 9:16, 4:3, 3:2
    additional_tags: Optional[str] = None  # 추가 태그


class PromptOptimizationResponse(BaseModel):
    """프롬프트 최적화 응답"""
    optimized_prompt: str  # 최적화된 영문 프롬프트
    negative_prompt: str  # 네거티브 프롬프트
    style_tags: list[str]  # 스타일 관련 태그
    quality_tags: list[str]  # 품질 관련 태그
    metadata: Dict[str, Any]  # 메타데이터


class PromptOptimizationService:
    """프롬프트 최적화 서비스"""
    
    def __init__(self):
        self.use_mock = not bool(settings.OPENAI_API_KEY and openai_client)
        self.style_presets = self._load_style_presets()
        self.quality_presets = self._load_quality_presets()
        self.negative_presets = self._load_negative_presets()
        
        logger.info(f"Prompt Optimization Service initialized (Mock mode: {self.use_mock})")
    
    async def optimize_prompt(self, request: PromptOptimizationRequest) -> PromptOptimizationResponse:
        """프롬프트 최적화"""
        
        if not self.use_mock and openai_client:
            return await self._optimize_with_openai(request)
        else:
            return await self._optimize_with_mock(request)
    
    async def _optimize_with_openai(self, request: PromptOptimizationRequest) -> PromptOptimizationResponse:
        """OpenAI를 사용한 실제 프롬프트 최적화"""
        
        try:
            # 시스템 프롬프트 구성
            system_prompt = f"""
            당신은 ComfyUI/Stable Diffusion을 위한 전문 프롬프트 엔지니어입니다.
            사용자의 입력을 받아 고품질 이미지 생성을 위한 최적화된 영문 프롬프트를 생성하세요.

            요구사항:
            1. 입력이 한글이면 영어로 번역
            2. ComfyUI에 최적화된 키워드와 태그 사용
            3. {request.style} 스타일 적용
            4. {request.quality_level} 품질 수준 적용
            5. 구체적이고 시각적인 묘사 포함

            응답 형식 (JSON):
            {{
                "optimized_prompt": "최적화된 영문 프롬프트",
                "negative_prompt": "네거티브 프롬프트",
                "style_tags": ["스타일", "관련", "태그"],
                "quality_tags": ["품질", "관련", "태그"],
                "reasoning": "최적화 과정 설명"
            }}
            """
            
            # 사용자 프롬프트 구성
            user_prompt = f"""
            원본 프롬프트: {request.original_prompt}
            스타일: {request.style}
            품질 수준: {request.quality_level}
            종횡비: {request.aspect_ratio}
            추가 태그: {request.additional_tags or "없음"}
            
            위 정보를 바탕으로 ComfyUI에 최적화된 프롬프트를 생성해주세요.
            """
            
            response = openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=settings.OPENAI_MAX_TOKENS,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            
            # JSON 파싱 시도
            try:
                parsed_result = json.loads(content)
                
                return PromptOptimizationResponse(
                    optimized_prompt=parsed_result.get("optimized_prompt", ""),
                    negative_prompt=parsed_result.get("negative_prompt", self.negative_presets["default"]),
                    style_tags=parsed_result.get("style_tags", []),
                    quality_tags=parsed_result.get("quality_tags", []),
                    metadata={
                        "method": "openai",
                        "model": settings.OPENAI_MODEL,
                        "reasoning": parsed_result.get("reasoning", ""),
                        "tokens_used": response.usage.total_tokens if response.usage else 0
                    }
                )
                
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 텍스트 처리
                return PromptOptimizationResponse(
                    optimized_prompt=content,
                    negative_prompt=self.negative_presets["default"],
                    style_tags=self.style_presets[request.style]["tags"],
                    quality_tags=self.quality_presets[request.quality_level]["tags"],
                    metadata={
                        "method": "openai_fallback",
                        "note": "JSON 파싱 실패, 원본 응답 사용"
                    }
                )
                
        except Exception as e:
            logger.error(f"OpenAI 프롬프트 최적화 실패: {e}")
            # 실패 시 Mock 모드로 fallback
            return await self._optimize_with_mock(request)
    
    async def _optimize_with_mock(self, request: PromptOptimizationRequest) -> PromptOptimizationResponse:
        """Mock 프롬프트 최적화"""
        
        # 간단한 규칙 기반 최적화
        original = request.original_prompt.strip()
        
        # 기본 영문 변환 (실제로는 번역 API 사용)
        if self._is_korean(original):
            # 간단한 한글 키워드 매핑
            korean_mapping = {
                "고양이": "cat",
                "강아지": "dog", 
                "꽃": "flower",
                "산": "mountain",
                "바다": "ocean",
                "하늘": "sky",
                "구름": "cloud",
                "나무": "tree",
                "집": "house",
                "차": "car",
                "사람": "person",
                "여자": "woman",
                "남자": "man",
                "아이": "child",
                "음식": "food",
                "풍경": "landscape",
                "도시": "city"
            }
            
            translated = original
            for kr, en in korean_mapping.items():
                translated = translated.replace(kr, en)
        else:
            translated = original
        
        # 스타일 및 품질 태그 추가
        style_tags = self.style_presets[request.style]["tags"]
        quality_tags = self.quality_presets[request.quality_level]["tags"]
        
        # 최적화된 프롬프트 구성
        optimized_parts = [translated]
        optimized_parts.extend(style_tags)
        optimized_parts.extend(quality_tags)
        
        if request.additional_tags:
            optimized_parts.append(request.additional_tags)
        
        # 종횡비에 따른 태그 추가
        if request.aspect_ratio == "16:9":
            optimized_parts.append("wide shot, cinematic")
        elif request.aspect_ratio == "9:16":
            optimized_parts.append("portrait orientation, vertical")
        
        optimized_prompt = ", ".join(optimized_parts)
        
        return PromptOptimizationResponse(
            optimized_prompt=optimized_prompt,
            negative_prompt=self.negative_presets[request.style],
            style_tags=style_tags,
            quality_tags=quality_tags,
            metadata={
                "method": "mock",
                "original_language": "korean" if self._is_korean(original) else "english",
                "note": "Mock optimization - 실제 OpenAI API 키 설정 시 고품질 최적화됩니다"
            }
        )
    
    def _is_korean(self, text: str) -> bool:
        """한글 포함 여부 확인"""
        return any('\uac00' <= char <= '\ud7af' for char in text)
    
    def _load_style_presets(self) -> Dict[str, Dict]:
        """스타일 프리셋 로드"""
        return {
            "realistic": {
                "tags": ["photorealistic", "detailed", "high resolution", "sharp focus"],
                "description": "사실적인 사진 스타일"
            },
            "anime": {
                "tags": ["anime style", "manga", "cel shading", "vibrant colors"],
                "description": "애니메이션 스타일"
            },
            "artistic": {
                "tags": ["artistic", "painterly", "expressive", "creative"],
                "description": "예술적 스타일"
            },
            "photograph": {
                "tags": ["professional photography", "DSLR", "studio lighting", "commercial"],
                "description": "전문 사진 스타일"
            }
        }
    
    def _load_quality_presets(self) -> Dict[str, Dict]:
        """품질 프리셋 로드"""
        return {
            "low": {
                "tags": ["simple", "basic"],
                "description": "기본 품질"
            },
            "medium": {
                "tags": ["good quality", "detailed"],
                "description": "중간 품질"
            },
            "high": {
                "tags": ["high quality", "masterpiece", "best quality", "ultra detailed"],
                "description": "고품질"
            },
            "ultra": {
                "tags": ["masterpiece", "best quality", "ultra detailed", "8k", "perfect", "flawless"],
                "description": "최고 품질"
            }
        }
    
    def _load_negative_presets(self) -> Dict[str, str]:
        """네거티브 프롬프트 프리셋 로드"""
        return {
            "default": "low quality, blurry, distorted, deformed, ugly, bad anatomy, worst quality, low resolution",
            "realistic": "low quality, blurry, distorted, deformed, ugly, bad anatomy, worst quality, low resolution, cartoon, anime, painting",
            "anime": "low quality, blurry, distorted, deformed, ugly, bad anatomy, worst quality, low resolution, realistic, photograph",
            "artistic": "low quality, blurry, distorted, deformed, ugly, bad anatomy, worst quality, low resolution",
            "photograph": "low quality, blurry, distorted, deformed, ugly, bad anatomy, worst quality, low resolution, cartoon, anime, painting, artistic"
        }


# 싱글톤 패턴
_prompt_optimization_service_instance = None

def get_prompt_optimization_service() -> PromptOptimizationService:
    """프롬프트 최적화 서비스 인스턴스 반환"""
    global _prompt_optimization_service_instance
    if _prompt_optimization_service_instance is None:
        _prompt_optimization_service_instance = PromptOptimizationService()
    return _prompt_optimization_service_instance