"""
RunPod Serverless 관리 서비스
RunPod API를 사용하여 여러 타입의 serverless endpoint를 동적으로 생성/관리
TTS, vLLM, Fine-tuning 각각의 엔드포인트를 별도로 관리
"""

import os
import json
import logging
import httpx
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
import os
from dotenv import load_dotenv
from abc import ABC, abstractmethod

load_dotenv()

logger = logging.getLogger(__name__)


class RunPodManagerError(Exception):
    """RunPod 관리자 오류"""
    pass


ServiceType = Literal["tts", "vllm", "finetuning"]


class BaseRunPodManager(ABC):
    """RunPod 엔드포인트 관리자 베이스 클래스"""
    
    def __init__(self, service_type: ServiceType):
        self.api_key = os.getenv("RUNPOD_API_KEY", "")
        self.base_url = "https://api.runpod.io/graphql"
        self.service_type = service_type
        
        if not self.api_key:
            raise RunPodManagerError("RUNPOD_API_KEY가 설정되지 않았습니다")
    
    @property
    @abstractmethod
    def docker_image(self) -> str:
        """Docker 이미지명"""
        pass
    
    @property
    @abstractmethod
    def endpoint_name(self) -> str:
        """엔드포인트 이름"""
        pass
    
    @property
    @abstractmethod
    def container_disk_size(self) -> int:
        """컨테이너 디스크 크기 (GB)"""
        pass
    
    @property
    @abstractmethod
    def env_vars(self) -> List[Dict[str, str]]:
        """환경 변수"""
        pass
    
    @property
    @abstractmethod
    def search_keywords(self) -> List[str]:
        """엔드포인트 검색용 키워드"""
        pass
    
    @property
    def headers(self) -> Dict[str, str]:
        """API 요청 헤더"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def list_endpoints(self) -> List[Dict[str, Any]]:
        """모든 serverless 엔드포인트 목록 조회"""
        query = """
        query {
            myself {
                endpoints {
                    id
                    name
                    templateId
                    workersMin
                    workersMax
                    template {
                        id
                        name
                        imageName
                        containerDiskInGb
                        volumeInGb
                    }
                }
            }
        }
        """
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": query}
                )
                
                if response.status_code != 200:
                    raise RunPodManagerError(f"엔드포인트 목록 조회 실패: {response.text}")
                
                data = response.json()
                
                if "errors" in data:
                    logger.error(f"GraphQL 오류: {data['errors']}")
                    raise RunPodManagerError(f"엔드포인트 조회 오류: {data['errors']}")
                
                endpoints = data.get("data", {}).get("myself", {}).get("endpoints", [])
                
                logger.info(f"📋 RunPod 엔드포인트 목록: {len(endpoints)}개")
                return endpoints
                
        except Exception as e:
            logger.error(f"❌ 엔드포인트 목록 조회 실패: {e}")
            raise RunPodManagerError(f"엔드포인트 목록 조회 실패: {e}")
    
    async def find_endpoint(self) -> Optional[Dict[str, Any]]:
        """서비스별 엔드포인트 찾기"""
        try:
            endpoints = await self.list_endpoints()
            
            for endpoint in endpoints:
                logger.info(f"엔드포인트 정보: {endpoint}")
                template = endpoint.get("template", {})
                
                # 다양한 조건으로 매칭 시도
                image_name = template.get("imageName", "")
                endpoint_name = endpoint.get("name", "")
                template_name = template.get("name", "")
                
                # Docker 이미지 정확 매칭 우선
                if self.docker_image in image_name or image_name in self.docker_image:
                    logger.info(f"✅ 기존 엔드포인트 찾음 (이미지 매칭): {endpoint['id']}")
                    logger.info(f"   - 엔드포인트 이름: {endpoint_name}")
                    logger.info(f"   - 템플릿 이름: {template_name}")
                    logger.info(f"   - Docker 이미지: {image_name}")
                    return endpoint
                
                # 키워드 매칭
                for keyword in self.search_keywords:
                    if (keyword in image_name.lower() or
                        keyword in endpoint_name.lower() or
                        keyword in template_name.lower()):
                        logger.info(f"✅ 기존 엔드포인트 찾음 (키워드 '{keyword}' 매칭): {endpoint['id']}")
                        logger.info(f"   - 엔드포인트 이름: {endpoint_name}")
                        logger.info(f"   - 템플릿 이름: {template_name}")
                        logger.info(f"   - Docker 이미지: {image_name}")
                        return endpoint
            
            logger.info(f"ℹ️ {self.service_type} 엔드포인트를 찾을 수 없습니다")
            return None
            
        except Exception as e:
            logger.error(f"❌ {self.service_type} 엔드포인트 검색 실패: {e}")
            return None
    
    async def create_template(self) -> Dict[str, Any]:
        """새로운 serverless 템플릿 생성"""
        mutation = """
        mutation saveTemplate($input: SaveTemplateInput!) {
            saveTemplate(input: $input) {
                id
                name
                imageName
                containerDiskInGb
            }
        }
        """
        
        variables = {
            "input": {
                "name": self.endpoint_name,
                "imageName": self.docker_image,
                "dockerArgs": "",  # Required field
                "containerDiskInGb": self.container_disk_size,
                "volumeInGb": 0,
                "ports": "8000/http",
                "env": self.env_vars,
                "isServerless": True
            }
        }
        
        try:
            logger.info(f"📝 새 RunPod 템플릿 생성 중: {self.endpoint_name}")
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": mutation, "variables": variables}
                )
                
                if response.status_code != 200:
                    raise RunPodManagerError(f"템플릿 생성 실패: {response.text}")
                
                data = response.json()
                
                if "errors" in data:
                    raise RunPodManagerError(f"GraphQL 오류: {data['errors']}")
                
                template = data.get("data", {}).get("saveTemplate")
                
                if not template:
                    raise RunPodManagerError("템플릿 생성 응답이 비어있습니다")
                
                logger.info(f"✅ 템플릿 생성 완료: {template['id']}")
                return template
                
        except Exception as e:
            logger.error(f"❌ 템플릿 생성 실패: {e}")
            raise RunPodManagerError(f"템플릿 생성 실패: {e}")
    
    async def create_endpoint(self, template_id: str) -> Dict[str, Any]:
        """템플릿을 사용하여 새로운 serverless 엔드포인트 생성"""
        mutation = """
        mutation {
            saveEndpoint(input: {
                templateId: "%s"
                name: "%s"
                workersMin: 0
                workersMax: 3
                idleTimeout: 5
                locations: "US"
                networkVolumeId: ""
                scalerType: "QUEUE_DELAY"
                scalerValue: 4
            }) {
                id
                name
                templateId
                workersMin
                workersMax
            }
        }
        """ % (template_id, self.endpoint_name)
        
        try:
            logger.info(f"🚀 템플릿 {template_id}를 사용하여 엔드포인트 생성 중")
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": mutation}
                )
                
                if response.status_code != 200:
                    raise RunPodManagerError(f"엔드포인트 생성 실패: {response.text}")
                
                data = response.json()
                
                if "errors" in data:
                    raise RunPodManagerError(f"GraphQL 오류: {data['errors']}")
                
                endpoint = data.get("data", {}).get("saveEndpoint")
                
                if not endpoint:
                    raise RunPodManagerError("엔드포인트 생성 응답이 비어있습니다")
                
                logger.info(f"✅ 엔드포인트 생성 완료: {endpoint['id']}")
                return endpoint
                
        except Exception as e:
            logger.error(f"❌ 엔드포인트 생성 실패: {e}")
            raise RunPodManagerError(f"엔드포인트 생성 실패: {e}")
    
    async def get_or_create_endpoint(self) -> Dict[str, Any]:
        """엔드포인트 가져오기 또는 생성"""
        try:
            # 기존 엔드포인트 찾기
            endpoint = await self.find_endpoint()
            
            if endpoint:
                logger.info(f"♻️ 기존 엔드포인트 사용: {endpoint['id']}")
                # 환경 변수에 저장
                os.environ["RUNPOD_ENDPOINT_ID"] = endpoint["id"]
                return endpoint
            
            # 엔드포인트를 찾지 못한 경우
            logger.error("❌ zonos-tts-worker 엔드포인트를 찾을 수 없습니다")
            logger.info("💡 RunPod 대시보드에서 다음 설정으로 엔드포인트를 생성하세요:")
            logger.info(f"   - Docker 이미지: {self.docker_image}")
            logger.info(f"   - 컨테이너 크기: {self.container_disk_size}GB")
            logger.info("   - 또는 기존 엔드포인트가 있다면 이름이나 Docker 이미지를 확인하세요")
            
            raise RunPodManagerError(
                "zonos-tts-worker 엔드포인트를 찾을 수 없습니다. "
                "RunPod 대시보드에서 엔드포인트를 생성하거나 기존 엔드포인트 설정을 확인하세요."
            )
            
        except Exception as e:
            logger.error(f"❌ 엔드포인트 가져오기/생성 실패: {e}")
            raise RunPodManagerError(f"엔드포인트 관리 실패: {e}")
    
    async def get_endpoint_status(self, endpoint_id: str) -> Dict[str, Any]:
        """엔드포인트 상태 확인"""
        query = """
        query GetEndpointStatus($endpointId: String!) {
            endpoint(id: $endpointId) {
                id
                name
                workersMin
                workersMax
                workersRunning
                workersThrottled
                queuedRequests
                avgResponseTime
                template {
                    name
                    imageName
                }
            }
        }
        """
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={
                        "query": query,
                        "variables": {"endpointId": endpoint_id}
                    }
                )
                
                if response.status_code != 200:
                    raise RunPodManagerError(f"상태 확인 실패: {response.text}")
                
                data = response.json()
                
                if "errors" in data:
                    logger.error(f"GraphQL 오류: {data['errors']}")
                    return {"status": "error", "error": str(data['errors'])}
                
                status = data.get("data", {}).get("endpoint", {})
                
                logger.info(f"📊 엔드포인트 상태: {status}")
                return status
                
        except Exception as e:
            logger.error(f"❌ 엔드포인트 상태 확인 실패: {e}")
            return {"status": "error", "error": str(e)}


# 각 서비스별 구체적인 매니저 클래스
class TTSRunPodManager(BaseRunPodManager):
    """TTS 서비스용 RunPod 매니저"""
    
    def __init__(self):
        super().__init__("tts")
    
    @property
    def docker_image(self) -> str:
        return "fallsnowing/zonos-tts-worker"
    
    @property
    def endpoint_name(self) -> str:
        return "zonos-tts-worker"
    
    @property
    def container_disk_size(self) -> int:
        return 50  # GB
    
    @property
    def env_vars(self) -> List[Dict[str, str]]:
        return [
            {"key": "MODEL_NAME", "value": "zonos-tts"},
            {"key": "LANGUAGE", "value": "ko"}
        ]
    
    @property
    def search_keywords(self) -> List[str]:
        return ["zonos", "tts", "voice", "speech"]


class VLLMRunPodManager(BaseRunPodManager):
    """vLLM 서비스용 RunPod 매니저"""
    
    def __init__(self):
        super().__init__("vllm")
    
    @property
    def docker_image(self) -> str:
        return "fallsnowing/vllm-lora-worker"  # 실제 이미지명으로 변경 필요
    
    @property
    def endpoint_name(self) -> str:
        return "vllm-lora-worker"
    
    @property
    def container_disk_size(self) -> int:
        return 100  # GB - vLLM은 더 큰 저장소가 필요
    
    @property
    def env_vars(self) -> List[Dict[str, str]]:
        return [
            {"key": "MODEL_NAME", "value": "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"},
            {"key": "MAX_MODEL_LEN", "value": "4096"},
            {"key": "TENSOR_PARALLEL_SIZE", "value": "1"},
            {"key": "GPU_MEMORY_UTILIZATION", "value": "0.85"},
            {"key": "DISABLE_V2_BLOCK_MANAGER", "value": "true"},
            {"key": "VLLM_ENGINE_ARGS", "value": "--gpu-memory-utilization 0.85 --max-model-len 4096"},
            {"key": "PYTORCH_CUDA_ALLOC_CONF", "value": "expandable_segments:True"}
        ]
    
    @property
    def search_keywords(self) -> List[str]:
        return ["vllm", "llama", "lora", "generation", "chat"]


class FinetuningRunPodManager(BaseRunPodManager):
    """Fine-tuning 서비스용 RunPod 매니저"""
    
    def __init__(self):
        super().__init__("finetuning")
    
    @property
    def docker_image(self) -> str:
        return "fallsnowing/finetuning-worker"  # 실제 이미지명으로 변경 필요
    
    @property
    def endpoint_name(self) -> str:
        return "finetuning-worker"
    
    @property
    def container_disk_size(self) -> int:
        return 200  # GB - Fine-tuning은 더 많은 저장소가 필요
    
    @property
    def env_vars(self) -> List[Dict[str, str]]:
        return [
            {"key": "BASE_MODEL", "value": "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"},
            {"key": "TRAINING_FRAMEWORK", "value": "axolotl"},
            {"key": "MAX_STEPS", "value": "1000"},
            {"key": "GPU_MEMORY_UTILIZATION", "value": "0.85"},
            {"key": "DISABLE_V2_BLOCK_MANAGER", "value": "true"},
            {"key": "VLLM_ENGINE_ARGS", "value": "--gpu-memory-utilization 0.85 --max-model-len 4096"},
            {"key": "PYTORCH_CUDA_ALLOC_CONF", "value": "expandable_segments:True"}
        ]
    
    @property
    def search_keywords(self) -> List[str]:
        return ["finetuning", "training", "axolotl", "lora", "qlora"]


# 기존 RunPodManager를 BaseRunPodManager 상속으로 변경 (하위 호환성)
class RunPodManager(TTSRunPodManager):
    """기존 RunPodManager - TTS 매니저의 별칭 (하위 호환성)"""
    pass


# 싱글톤 인스턴스들
_tts_manager = None
_vllm_manager = None
_finetuning_manager = None
_runpod_manager = None  # 기존 호환성


def get_tts_manager() -> TTSRunPodManager:
    """TTS RunPod 매니저 싱글톤 인스턴스 반환"""
    global _tts_manager
    if _tts_manager is None:
        _tts_manager = TTSRunPodManager()
    return _tts_manager


def get_vllm_manager() -> VLLMRunPodManager:
    """vLLM RunPod 매니저 싱글톤 인스턴스 반환"""
    global _vllm_manager
    if _vllm_manager is None:
        _vllm_manager = VLLMRunPodManager()
    return _vllm_manager


def get_finetuning_manager() -> FinetuningRunPodManager:
    """Fine-tuning RunPod 매니저 싱글톤 인스턴스 반환"""
    global _finetuning_manager
    if _finetuning_manager is None:
        _finetuning_manager = FinetuningRunPodManager()
    return _finetuning_manager


def get_runpod_manager() -> RunPodManager:
    """기존 RunPod 관리자 싱글톤 인스턴스 반환 (하위 호환성)"""
    global _runpod_manager
    if _runpod_manager is None:
        _runpod_manager = RunPodManager()
    return _runpod_manager


def get_manager_by_service_type(service_type: ServiceType) -> BaseRunPodManager:
    """서비스 타입별 매니저 반환"""
    if service_type == "tts":
        return get_tts_manager()
    elif service_type == "vllm":
        return get_vllm_manager()
    elif service_type == "finetuning":
        return get_finetuning_manager()
    else:
        raise ValueError(f"지원하지 않는 서비스 타입: {service_type}")


# 서버 시작 시 초기화 함수
async def initialize_runpod():
    """서버 시작 시 RunPod 다중 서비스 초기화"""
    try:
        logger.info("🏁 RunPod 다중 서비스 초기화 시작")
        
        # API 키 확인
        if not os.getenv("RUNPOD_API_KEY"):
            logger.warning("⚠️ RUNPOD_API_KEY가 설정되지 않았습니다. RunPod 기능이 비활성화됩니다.")
            return None
        
        initialized_services = {}
        
        # TTS 서비스 초기화
        try:
            logger.info("🎤 TTS 서비스 초기화 중...")
            tts_manager = get_tts_manager()
            tts_endpoint = await tts_manager.get_or_create_endpoint()
            
            if tts_endpoint:
                initialized_services["tts"] = tts_endpoint
                os.environ["RUNPOD_TTS_ENDPOINT_ID"] = tts_endpoint["id"]
                logger.info(f"✅ TTS 서비스 초기화 완료: {tts_endpoint['id']}")
            else:
                logger.warning("⚠️ TTS 엔드포인트 초기화 실패")
        except Exception as e:
            logger.warning(f"⚠️ TTS 서비스 초기화 실패: {e}")
        
        # vLLM 서비스 초기화 (선택적)
        try:
            logger.info("🤖 vLLM 서비스 초기화 중...")
            vllm_manager = get_vllm_manager()
            vllm_endpoint = await vllm_manager.find_endpoint()  # 생성하지 말고 찾기만
            
            if vllm_endpoint:
                initialized_services["vllm"] = vllm_endpoint
                os.environ["RUNPOD_VLLM_ENDPOINT_ID"] = vllm_endpoint["id"]
                logger.info(f"✅ vLLM 서비스 발견됨: {vllm_endpoint['id']}")
            else:
                logger.info("ℹ️ vLLM 엔드포인트를 찾을 수 없습니다 (필요시 수동 생성)")
        except Exception as e:
            logger.info(f"ℹ️ vLLM 서비스 확인 실패: {e}")
        
        # Fine-tuning 서비스 초기화 (선택적)
        try:
            logger.info("🏋️ Fine-tuning 서비스 초기화 중...")
            finetuning_manager = get_finetuning_manager()
            finetuning_endpoint = await finetuning_manager.find_endpoint()  # 생성하지 말고 찾기만
            
            if finetuning_endpoint:
                initialized_services["finetuning"] = finetuning_endpoint
                os.environ["RUNPOD_FINETUNING_ENDPOINT_ID"] = finetuning_endpoint["id"]
                logger.info(f"✅ Fine-tuning 서비스 발견됨: {finetuning_endpoint['id']}")
            else:
                logger.info("ℹ️ Fine-tuning 엔드포인트를 찾을 수 없습니다 (필요시 수동 생성)")
        except Exception as e:
            logger.info(f"ℹ️ Fine-tuning 서비스 확인 실패: {e}")
        
        # 하위 호환성을 위해 TTS 엔드포인트를 기본값으로 설정
        if "tts" in initialized_services:
            os.environ["RUNPOD_ENDPOINT_ID"] = initialized_services["tts"]["id"]
        
        if initialized_services:
            logger.info(f"✅ RunPod 초기화 완료: {list(initialized_services.keys())} 서비스")
            return initialized_services
        else:
            logger.warning("⚠️ RunPod 서비스 초기화 실패 (TTS 기능이 제한될 수 있습니다)")
            return None
            
    except Exception as e:
        logger.error(f"❌ RunPod 초기화 중 오류: {e}")
        return None


async def initialize_service(service_type: ServiceType, create_if_missing: bool = False):
    """특정 서비스 초기화"""
    try:
        logger.info(f"🔧 {service_type} 서비스 초기화 중...")
        
        manager = get_manager_by_service_type(service_type)
        
        if create_if_missing:
            endpoint = await manager.get_or_create_endpoint()
        else:
            endpoint = await manager.find_endpoint()
        
        if endpoint:
            env_key = f"RUNPOD_{service_type.upper()}_ENDPOINT_ID"
            os.environ[env_key] = endpoint["id"]
            logger.info(f"✅ {service_type} 서비스 초기화 완료: {endpoint['id']}")
            return endpoint
        else:
            logger.warning(f"⚠️ {service_type} 엔드포인트를 찾을 수 없습니다")
            return None
            
    except Exception as e:
        logger.error(f"❌ {service_type} 서비스 초기화 실패: {e}")
        return None