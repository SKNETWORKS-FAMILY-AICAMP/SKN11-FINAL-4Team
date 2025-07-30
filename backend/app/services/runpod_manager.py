"""
RunPod Serverless 관리 서비스
RunPod API를 사용하여 serverless endpoint를 동적으로 생성/관리
"""

import os
import json
import logging
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class RunPodManagerError(Exception):
    """RunPod 관리자 오류"""
    pass


class RunPodManager:
    """RunPod Serverless 엔드포인트 관리자"""
    
    def __init__(self):
        self.api_key = os.getenv("RUNPOD_API_KEY", "")
        self.base_url = "https://api.runpod.io/graphql"
        self.docker_image = "fallsnowing/zonos-tts-worker"
        self.endpoint_name = "zonos-tts-worker"
        self.container_disk_size = 50  # GB
        
        if not self.api_key:
            raise RunPodManagerError("RUNPOD_API_KEY가 설정되지 않았습니다")
    
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
        """zonos-tts-worker 엔드포인트 찾기"""
        try:
            endpoints = await self.list_endpoints()
            
            for endpoint in endpoints:
                logger.info(f"엔드포인트 정보: {endpoint}")
                template = endpoint.get("template", {})
                
                # 다양한 조건으로 매칭 시도
                image_name = template.get("imageName", "")
                endpoint_name = endpoint.get("name", "")
                template_name = template.get("name", "")
                
                # Docker 이미지명이나 엔드포인트 이름에 "zonos" 또는 "tts"가 포함되어 있는지 확인
                if (self.docker_image in image_name or 
                    image_name in self.docker_image or
                    "zonos" in image_name.lower() or
                    "tts" in image_name.lower() or
                    "zonos" in endpoint_name.lower() or
                    "tts" in endpoint_name.lower() or
                    "zonos" in template_name.lower() or
                    "tts" in template_name.lower()):
                    logger.info(f"✅ 기존 엔드포인트 찾음: {endpoint['id']}")
                    logger.info(f"   - 엔드포인트 이름: {endpoint_name}")
                    logger.info(f"   - 템플릿 이름: {template_name}")
                    logger.info(f"   - Docker 이미지: {image_name}")
                    return endpoint
            
            logger.info("ℹ️ 기존 엔드포인트를 찾을 수 없습니다")
            return None
            
        except Exception as e:
            logger.error(f"❌ 엔드포인트 검색 실패: {e}")
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
                "env": [
                    {"key": "MODEL_NAME", "value": "zonos-tts"},
                    {"key": "LANGUAGE", "value": "ko"}
                ],
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


# 싱글톤 인스턴스
_runpod_manager = None


def get_runpod_manager() -> RunPodManager:
    """RunPod 관리자 싱글톤 인스턴스 반환"""
    global _runpod_manager
    if _runpod_manager is None:
        _runpod_manager = RunPodManager()
    return _runpod_manager


# 서버 시작 시 초기화 함수
async def initialize_runpod():
    """서버 시작 시 RunPod 초기화"""
    try:
        logger.info("🏁 RunPod 초기화 시작")
        
        # API 키 확인
        if not os.getenv("RUNPOD_API_KEY"):
            logger.warning("⚠️ RUNPOD_API_KEY가 설정되지 않았습니다. RunPod 기능이 비활성화됩니다.")
            return None
        
        # 관리자 생성
        manager = get_runpod_manager()
        
        # 엔드포인트 확인/생성
        endpoint = await manager.get_or_create_endpoint()
        
        if endpoint:
            logger.info(f"✅ RunPod 초기화 완료: {endpoint['id']}")
            logger.info(f"   - 이름: {endpoint.get('name')}")
            logger.info(f"   - Docker 이미지: {endpoint.get('dockerImage')}")
            logger.info(f"   - 디스크 크기: {endpoint.get('containerDiskInGb')}GB")
            
            # 엔드포인트 ID 환경 변수 설정
            os.environ["RUNPOD_ENDPOINT_ID"] = endpoint["id"]
            
            return endpoint
        else:
            logger.error("❌ RunPod 엔드포인트 초기화 실패")
            return None
            
    except Exception as e:
        logger.error(f"❌ RunPod 초기화 중 오류: {e}")
        return None