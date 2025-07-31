"""
지능형 요청 라우팅 시스템
요청 특성에 따라 적절한 RunPod Worker로 라우팅
"""
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
import asyncio
from datetime import datetime, timedelta

from app.utils.runpod_client import RunPodEndpoint, get_runpod_client

logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    """작업 우선순위"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class RoutingDecision:
    """라우팅 결정 정보"""
    endpoint: RunPodEndpoint
    priority: TaskPriority
    estimated_time: int  # 예상 처리 시간 (초)
    gpu_requirement: str  # GPU 요구사항
    cost_estimate: float  # 예상 비용
    
class IntelligentRouter:
    """지능형 라우팅 시스템"""
    
    def __init__(self):
        self.runpod_client = get_runpod_client()
        self._endpoint_stats = {
            endpoint: {
                "total_requests": 0,
                "failed_requests": 0,
                "avg_processing_time": 0,
                "last_health_check": None,
                "is_healthy": True
            }
            for endpoint in RunPodEndpoint
        }
        self._start_health_monitoring()
    
    def _start_health_monitoring(self):
        """백그라운드 헬스 체크 시작"""
        asyncio.create_task(self._health_check_loop())
    
    async def _health_check_loop(self):
        """주기적인 헬스 체크"""
        while True:
            for endpoint in RunPodEndpoint:
                try:
                    is_healthy = await self.runpod_client.health_check(endpoint)
                    self._endpoint_stats[endpoint]["is_healthy"] = is_healthy
                    self._endpoint_stats[endpoint]["last_health_check"] = datetime.utcnow()
                except Exception as e:
                    logger.error(f"헬스 체크 실패 {endpoint}: {e}")
                    self._endpoint_stats[endpoint]["is_healthy"] = False
            
            await asyncio.sleep(30)  # 30초마다 체크
    
    async def route_request(
        self,
        request_type: str,
        request_data: Dict[str, Any],
        user_tier: str = "free"
    ) -> RoutingDecision:
        """요청을 분석하여 최적의 엔드포인트로 라우팅"""
        
        # 요청 타입별 라우팅
        if request_type == "tts":
            return await self._route_tts_request(request_data, user_tier)
        elif request_type == "generation":
            return await self._route_generation_request(request_data, user_tier)
        elif request_type == "embedding":
            return await self._route_embedding_request(request_data, user_tier)
        elif request_type == "finetuning":
            return await self._route_finetuning_request(request_data, user_tier)
        else:
            raise ValueError(f"알 수 없는 요청 타입: {request_type}")
    
    async def _route_tts_request(
        self,
        request_data: Dict[str, Any],
        user_tier: str
    ) -> RoutingDecision:
        """TTS 요청 라우팅"""
        text_length = len(request_data.get("text", ""))
        has_voice_cloning = "voice_data_base64" in request_data
        
        # 복잡도 계산
        if has_voice_cloning:
            estimated_time = 15 + (text_length / 100) * 5
            gpu_requirement = "RTX 3090"
            priority = TaskPriority.HIGH
        else:
            estimated_time = 5 + (text_length / 100) * 2
            gpu_requirement = "RTX 3090"
            priority = TaskPriority.MEDIUM
        
        # 사용자 등급에 따른 우선순위 조정
        if user_tier == "premium":
            priority = TaskPriority(min(priority.value + 1, TaskPriority.CRITICAL.value))
        
        # 비용 계산 (RunPod 가격 기준 예시)
        cost_per_second = 0.00011  # RTX 3090 시간당 $0.40
        cost_estimate = estimated_time * cost_per_second
        
        return RoutingDecision(
            endpoint=RunPodEndpoint.TTS,
            priority=priority,
            estimated_time=estimated_time,
            gpu_requirement=gpu_requirement,
            cost_estimate=cost_estimate
        )
    
    async def _route_generation_request(
        self,
        request_data: Dict[str, Any],
        user_tier: str
    ) -> RoutingDecision:
        """LLM 생성 요청 라우팅"""
        max_tokens = request_data.get("max_tokens", 512)
        has_lora = "lora_adapter" in request_data
        
        # 복잡도 계산
        if max_tokens > 2000:
            estimated_time = 30 + (max_tokens / 100) * 2
            gpu_requirement = "A100"
            priority = TaskPriority.HIGH
        else:
            estimated_time = 10 + (max_tokens / 100)
            gpu_requirement = "A100"
            priority = TaskPriority.MEDIUM
        
        if has_lora:
            estimated_time *= 1.2  # LoRA 사용시 20% 증가
        
        # 비용 계산
        cost_per_second = 0.00028  # A100 시간당 $1.00
        cost_estimate = estimated_time * cost_per_second
        
        return RoutingDecision(
            endpoint=RunPodEndpoint.LLM,
            priority=priority,
            estimated_time=estimated_time,
            gpu_requirement=gpu_requirement,
            cost_estimate=cost_estimate
        )
    
    async def _route_embedding_request(
        self,
        request_data: Dict[str, Any],
        user_tier: str
    ) -> RoutingDecision:
        """임베딩 요청 라우팅"""
        texts = request_data.get("texts", [])
        num_texts = len(texts) if isinstance(texts, list) else 1
        
        estimated_time = 2 + (num_texts * 0.5)
        gpu_requirement = "RTX 3090"
        priority = TaskPriority.LOW
        
        # 배치 크기가 크면 우선순위 증가
        if num_texts > 100:
            priority = TaskPriority.MEDIUM
        
        cost_per_second = 0.00011
        cost_estimate = estimated_time * cost_per_second
        
        return RoutingDecision(
            endpoint=RunPodEndpoint.EMBEDDING,
            priority=priority,
            estimated_time=estimated_time,
            gpu_requirement=gpu_requirement,
            cost_estimate=cost_estimate
        )
    
    async def _route_finetuning_request(
        self,
        request_data: Dict[str, Any],
        user_tier: str
    ) -> RoutingDecision:
        """파인튜닝 요청 라우팅"""
        num_epochs = request_data.get("num_epochs", 3)
        dataset_size = request_data.get("dataset_size", 1000)
        
        # 파인튜닝은 시간이 오래 걸림
        estimated_time = 600 * num_epochs * (dataset_size / 1000)
        gpu_requirement = "A100"  # 멀티 GPU 가능
        priority = TaskPriority.LOW  # 배치 작업
        
        # Premium 사용자는 우선순위 증가
        if user_tier == "premium":
            priority = TaskPriority.MEDIUM
        
        cost_per_second = 0.00056  # A100 x2 시간당 $2.00
        cost_estimate = estimated_time * cost_per_second
        
        return RoutingDecision(
            endpoint=RunPodEndpoint.FINETUNING,
            priority=priority,
            estimated_time=estimated_time,
            gpu_requirement=gpu_requirement,
            cost_estimate=cost_estimate
        )
    
    def get_endpoint_stats(self) -> Dict[str, Any]:
        """엔드포인트 통계 반환"""
        return self._endpoint_stats
    
    async def execute_with_fallback(
        self,
        routing_decision: RoutingDecision,
        request_data: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """장애 복구 기능이 있는 실행"""
        endpoint = routing_decision.endpoint
        
        for attempt in range(max_retries):
            try:
                # 엔드포인트가 건강한지 확인
                if not self._endpoint_stats[endpoint]["is_healthy"]:
                    logger.warning(f"{endpoint} 비정상, 대기 중...")
                    await asyncio.sleep(5)
                
                # 요청 실행
                start_time = datetime.utcnow()
                result = await self.runpod_client.run_sync(
                    endpoint=endpoint,
                    input_data=request_data,
                    timeout=routing_decision.estimated_time * 2
                )
                
                # 통계 업데이트
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                self._update_stats(endpoint, success=True, processing_time=processing_time)
                
                return result
                
            except Exception as e:
                logger.error(f"요청 실행 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                self._update_stats(endpoint, success=False)
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 지수 백오프
                else:
                    raise
    
    def _update_stats(
        self,
        endpoint: RunPodEndpoint,
        success: bool,
        processing_time: Optional[float] = None
    ):
        """통계 업데이트"""
        stats = self._endpoint_stats[endpoint]
        stats["total_requests"] += 1
        
        if not success:
            stats["failed_requests"] += 1
        elif processing_time:
            # 이동 평균 계산
            current_avg = stats["avg_processing_time"]
            total_requests = stats["total_requests"]
            stats["avg_processing_time"] = (
                (current_avg * (total_requests - 1) + processing_time) / total_requests
            )

# 싱글톤 인스턴스
_router = None

def get_intelligent_router() -> IntelligentRouter:
    """지능형 라우터 싱글톤 인스턴스 반환"""
    global _router
    if _router is None:
        _router = IntelligentRouter()
    return _router