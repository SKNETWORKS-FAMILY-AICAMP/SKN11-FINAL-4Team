"""
RunPod 서버 관리 서비스
ComfyUI가 설치된 서버 인스턴스를 동적으로 생성/관리
"""

import asyncio
import aiohttp
import logging
from typing import Dict, Optional, Any
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger(__name__)


class RunPodPodRequest(BaseModel):
    """RunPod 인스턴스 생성 요청"""
    name: str
    template_id: str
    gpu_type: str = "NVIDIA RTX A6000"
    gpu_count: int = 1
    container_disk_in_gb: int = 20
    volume_in_gb: int = 0
    ports: str = "8188/http"  # ComfyUI 기본 포트
    env: Dict[str, str] = {}


class RunPodPodResponse(BaseModel):
    """RunPod 인스턴스 정보"""
    pod_id: str
    status: str  # STARTING, RUNNING, STOPPED, FAILED
    runtime: Optional[Dict[str, Any]] = None
    endpoint_url: Optional[str] = None
    cost_per_hour: Optional[float] = None


class RunPodService:
    """RunPod API 서비스"""
    
    def __init__(self):
        self.api_key = settings.RUNPOD_API_KEY
        self.base_url = "https://api.runpod.io/graphql"
        self.template_id = settings.RUNPOD_TEMPLATE_ID
        
        # Mock 모드 제거 - 실제 API 키가 없으면 오류 발생
        if not self.api_key or not self.template_id:
            raise ValueError(
                f"RunPod 설정이 필요합니다: "
                f"API_KEY={'설정됨' if self.api_key else '없음'}, "
                f"TEMPLATE_ID={'설정됨' if self.template_id else '없음'}"
            )
        
        logger.info(f"RunPod Service initialized (API Key: {'***' + self.api_key[-4:] if len(self.api_key) > 4 else '***'}, Template: {self.template_id})")
    
    async def create_pod(self, request_id: str) -> RunPodPodResponse:
        """ComfyUI 서버 인스턴스 생성 (GPU 폴백 지원)"""
        
        # GPU 재시도 로직 - 가용성 확인된 모든 GPU 포함 (성공률 극대화)
        gpu_chain = [

            # RTX 4090 최우선 사용
            "NVIDIA GeForce RTX 4090",         # 24GB, $0.20 spot/$0.34 ondemand - 최고 성능
            
            # 고성능 대안 GPU들
            "NVIDIA RTX A6000",                # 48GB, $0.25 spot/$0.33 ondemand
            "NVIDIA A40",                      # 48GB, $0.24 spot/$0.35 ondemand
            "NVIDIA RTX A5000",                # 24GB, $0.11 spot/$0.16 ondemand
            "NVIDIA GeForce RTX 3090",         # 24GB, $0.11 spot/$0.22 ondemand
            
            # 중급 성능 GPU들
            "NVIDIA RTX A4500",                # 20GB, $0.10 spot/$0.19 ondemand
            "NVIDIA RTX 4000 Ada Generation",  # 20GB, $0.10 spot/$0.20 ondemand
            "NVIDIA RTX A4000",                # 16GB, $0.09 spot/$0.17 ondemand
            "NVIDIA GeForce RTX 4080 SUPER",   # 16GB, $0.17 spot/$0.28 ondemand
            "NVIDIA GeForce RTX 4080",         # 16GB, $0.16 spot/$0.27 ondemand
            
            # 경제적 선택 GPU들
            "NVIDIA GeForce RTX 4070 Ti",      # 12GB, $0.10 spot/$0.19 ondemand
            "Tesla V100-PCIE-16GB",            # 16GB, $0.10 spot/$0.19 ondemand
            "NVIDIA GeForce RTX 3080",         # 10GB, $0.09 spot/$0.17 ondemand
            "NVIDIA GeForce RTX 3070",         # 8GB, $0.07 spot/$0.13 ondemand
        ]
        
        for attempt in range(min(len(gpu_chain), 15)):  # 최대 15개 GPU 시도
            try:
                gpu_type = gpu_chain[attempt]
                
                logger.info(f"Pod 생성 시도 #{attempt + 1} - GPU: {gpu_type}")
                

                # 먼저 Interruptible(Spot) 인스턴스 시도, 실패시 On-Demand 시도
                pod_data = None
                for instance_type in ["interruptible", "on_demand"]:
                    try:
                        pod_data = await self._create_pod_with_type(gpu_type, request_id, instance_type)
                        if pod_data:
                            break
                    except Exception as type_error:
                        logger.warning(f"  → {instance_type} 실패: {type_error}")
                        continue
                
                if not pod_data:
                    if attempt < 3:
                        logger.warning(f"GPU {gpu_type} 모든 인스턴스 타입 실패 - 다음 GPU로 시도")
                        continue
                    else:
                        raise Exception("모든 GPU 옵션 실패")
                
                # Pod 데이터 처리 (기존 로직)
                endpoint_url = None
                if pod_data.get("runtime") and pod_data["runtime"].get("ports"):
                    for port in pod_data["runtime"]["ports"]:
                        if port["privatePort"] == 8188:
                            endpoint_url = f"http://{port['ip']}:{port['publicPort']}"
                            break
                
                logger.info(f"✅ RunPod 인스턴스 생성 성공 - GPU: {gpu_type}, Pod ID: {pod_data['id']}")
                
                # Pod 생성 후 자동으로 시작
                pod_id = pod_data["id"]
                logger.info(f"🚀 Pod {pod_id} 자동 시작 시도...")
                
                start_success = await self._start_pod(pod_id)
                if start_success:
                    logger.info(f"✅ Pod {pod_id} 자동 시작 성공")
                else:
                    logger.warning(f"⚠️ Pod {pod_id} 자동 시작 실패, 수동 시작 필요")
                
                return RunPodPodResponse(
                    pod_id=pod_id,
                    status="STARTING" if start_success else pod_data["desiredStatus"],
                    runtime=pod_data.get("runtime", {}),
                    endpoint_url=endpoint_url,
                    cost_per_hour=0.2
                )
                        
            except Exception as e:
                if attempt < 3 and "no longer any instances available" in str(e):
                    logger.warning(f"시도 #{attempt + 1} ({gpu_type}) 실패 - 다음 GPU로 재시도: {e}")
                    continue
                else:
                    logger.error(f"RunPod 인스턴스 생성 실패 (시도 #{attempt + 1}): {e}")
                    if attempt == 3:  # 마지막 시도 (4번째)
                        raise RuntimeError("지금 사용가능한 자원이 없습니다. 잠시 후 다시 시도해 주세요.")
                    elif "no longer any instances available" not in str(e):
                        # 인스턴스 부족이 아닌 다른 오류면 즉시 실패
                        raise RuntimeError(f"RunPod Pod 생성 실패: {e}")
        
        # 모든 시도 실패
        logger.error("모든 GPU 옵션으로 인스턴스 생성 실패")
        raise RuntimeError("지금 사용가능한 자원이 없습니다. 잠시 후 다시 시도해 주세요.")
    
    async def _create_pod_with_type(self, gpu_type: str, request_id: str, instance_type: str) -> dict:
        """특정 인스턴스 타입으로 Pod 생성"""
        
        if instance_type == "interruptible":
            # Spot 인스턴스 (기존 로직)
            mutation = """
            mutation podRentInterruptable($input: PodRentInterruptableInput!) {
                podRentInterruptable(input: $input) {
                    id
                    desiredStatus
                    runtime {
                        uptimeInSeconds
                        ports {
                            ip
                            isIpPublic
                            privatePort
                            publicPort
                        }
                    }
                    machine {
                        podHostId
                    }
                }
            }
            """
            
            variables = {
                "input": {
                    "bidPerGpu": 0.5,  # 시간당 최대 비용 (USD) - 여유있게 설정
                    "gpuCount": 1,
                    "volumeInGb": 200,
                    "volumeKey": settings.RUNPOD_VOLUME_ID,
                    "containerDiskInGb": 20,
                    "minVcpuCount": 1,
                    "minMemoryInGb": 4,
                    "gpuTypeId": gpu_type,
                    "name": "AIMEX_ComfyUI_Custom_py312_cu124",
                    "imageName": "runpod/pytorch:2.1.0-py3.10-cuda12.1.1-devel-ubuntu22.04",
                    "dockerArgs": "bash -c 'pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 && git clone https://github.com/comfyanonymous/ComfyUI.git /workspace/ComfyUI && cd /workspace/ComfyUI && pip install -r requirements.txt && python main.py --listen 0.0.0.0 --port 8188'",
                    "ports": "8188/http",
                    "volumeMountPath": "/workspace",
                    "dataCenterId": "EU-RO-1",
                    "env": [
                        {"key": "CUDA_VERSION", "value": "12.4"},
                        {"key": "JUPYTER_PASSWORD", "value": "rp123456789"},
                        {"key": "ENABLE_TENSORBOARD", "value": "1"},
                        {"key": "COMFYUI_MODEL_PATH", "value": "/workspace/models"},
                        {"key": "COMFYUI_OUTPUT_PATH", "value": "/workspace/output"}
                    ]
                }
            }
        else:  # on_demand
            # On-Demand 인스턴스 - 새로운 podFindAndDeployOnDemand mutation 사용
            mutation = """
            mutation podFindAndDeployOnDemand($input: PodFindAndDeployOnDemandInput!) {
                podFindAndDeployOnDemand(input: $input) {
                    id
                    desiredStatus
                    runtime {
                        uptimeInSeconds
                        ports {
                            ip
                            isIpPublic
                            privatePort
                            publicPort
                        }
                    }
                    machine {
                        podHostId
                    }
                }
            }
            """
            
            variables = {
                "input": {
                    "cloudType": "ALL",  # ALL, SECURE, COMMUNITY 옵션
                    "gpuCount": 1,
                    "volumeInGb": 200,
                    "volumeKey": settings.RUNPOD_VOLUME_ID,
                    "containerDiskInGb": 20,
                    "minVcpuCount": 1,
                    "minMemoryInGb": 4,
                    "gpuTypeId": gpu_type,
                    "name": "AIMEX_ComfyUI_Custom_py312_cu124",
                    "imageName": "runpod/pytorch:2.1.0-py3.10-cuda12.1.1-devel-ubuntu22.04",
                    "dockerArgs": "bash -c 'pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 && git clone https://github.com/comfyanonymous/ComfyUI.git /workspace/ComfyUI && cd /workspace/ComfyUI && pip install -r requirements.txt && python main.py --listen 0.0.0.0 --port 8188'",
                    "ports": "8188/http",
                    "volumeMountPath": "/workspace",
                    "dataCenterId": "EU-RO-1",
                    "env": [
                        {"key": "CUDA_VERSION", "value": "12.4"},
                        {"key": "JUPYTER_PASSWORD", "value": "rp123456789"},
                        {"key": "ENABLE_TENSORBOARD", "value": "1"},
                        {"key": "COMFYUI_MODEL_PATH", "value": "/workspace/models"},
                        {"key": "COMFYUI_OUTPUT_PATH", "value": "/workspace/output"}
                    ]
                }
            }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "query": mutation,
                "variables": variables
            }
            
            async with session.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    response_text = await response.text()
                    raise Exception(f"RunPod API 호출 실패: {response.status} - {response_text}")
                
                data = await response.json()
                
                if "errors" in data:
                    raise Exception(f"RunPod GraphQL 오류: {data['errors']}")
                
                if instance_type == "interruptible":
                    return data["data"]["podRentInterruptable"]
                else:
                    return data["data"]["podFindAndDeployOnDemand"]
    
    async def get_pod_status(self, pod_id: str) -> RunPodPodResponse:
        """Pod 상태 조회"""
        
        try:
            # GraphQL 쿼리 - Pod 상태 조회
            query = """
            query pod($input: PodFilter!) {
                pod(input: $input) {
                    id
                    desiredStatus
                    lastStatusChange
                    runtime {
                        uptimeInSeconds
                        ports {
                            ip
                            isIpPublic
                            privatePort
                            publicPort
                        }
                    }
                }
            }
            """
            
            variables = {
                "input": {
                    "podId": pod_id
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "query": query,
                    "variables": variables
                }
                
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        raise Exception(f"RunPod API 호출 실패: {response.status}")
                    
                    data = await response.json()
                    pod_data = data["data"]["pod"]
                    
                    # 엔드포인트 URL 구성
                    endpoint_url = None
                    if pod_data.get("runtime") and pod_data["runtime"].get("ports"):
                        for port in pod_data["runtime"]["ports"]:
                            if port["privatePort"] == 8188:
                                # ComfyUI는 HTTP 프로토콜 사용
                                endpoint_url = f"http://{port['ip']}:{port['publicPort']}"
                                break
                    
                    return RunPodPodResponse(
                        pod_id=pod_data["id"],
                        status=pod_data["desiredStatus"],
                        runtime=pod_data.get("runtime", {}),
                        endpoint_url=endpoint_url
                    )
                    
        except Exception as e:
            logger.error(f"RunPod 상태 조회 실패: {e}")
            raise RuntimeError(f"RunPod 상태 조회 실패: {e}")
    
    async def _start_pod(self, pod_id: str) -> bool:
        """Pod 시작 (자동화용)"""
        
        if not pod_id:
            logger.error("Pod ID가 제공되지 않음")
            return False
        
        try:
            logger.info(f"RunPod {pod_id} 시작 API 호출 중...")
            
            # GraphQL 뮤테이션 - Pod 시작 (새로 생성된 Pod용)
            mutation = """
            mutation podStart($input: PodStartInput!) {
                podStart(input: $input)
            }
            """
            
            variables = {
                "input": {
                    "podId": pod_id
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "query": mutation,
                    "variables": variables
                }
                
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    response_text = await response.text()
                    logger.info(f"RunPod 시작 API 응답: {response.status} - {response_text}")
                    
                    if response.status != 200:
                        logger.error(f"RunPod 시작 API 호출 실패: {response.status}")
                        return False
                    
                    try:
                        data = await response.json()
                        if "errors" in data:
                            logger.error(f"RunPod 시작 GraphQL 오류: {data['errors']}")
                            return False
                            
                        result = data.get("data", {}).get("podStart", False)
                        
                        if result:
                            logger.info(f"✅ RunPod {pod_id} 시작 요청 성공")
                            return True
                        else:
                            logger.error(f"❌ RunPod {pod_id} 시작 요청 실패: {data}")
                            return False
                            
                    except Exception as json_error:
                        logger.error(f"RunPod 시작 응답 JSON 파싱 실패: {json_error}")
                        return False
                    
        except asyncio.TimeoutError:
            logger.error(f"RunPod {pod_id} 시작 API 타임아웃")
            return False
        except Exception as e:
            logger.error(f"RunPod {pod_id} 시작 중 예외 발생: {e}")
            return False

    async def terminate_pod(self, pod_id: str) -> bool:
        """Pod 종료 (강화된 로직)"""
        
        if not pod_id:
            logger.error("Pod ID가 제공되지 않음")
            return False
        
        try:
            logger.info(f"RunPod {pod_id} 종료 API 호출 중...")
            
            # GraphQL 뮤테이션 - Pod 종료
            mutation = """
            mutation podTerminate($input: PodTerminateInput!) {
                podTerminate(input: $input)
            }
            """
            
            variables = {
                "input": {
                    "podId": pod_id
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "query": mutation,
                    "variables": variables
                }
                
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)  # 타임아웃 증가
                ) as response:
                    response_text = await response.text()
                    logger.info(f"RunPod API 응답: {response.status} - {response_text}")
                    
                    if response.status != 200:
                        logger.error(f"RunPod 종료 API 호출 실패: {response.status} - {response_text}")
                        return False
                    
                    try:
                        data = await response.json()
                        result = data.get("data", {}).get("podTerminate", False)
                        
                        if result:
                            logger.info(f"✅ RunPod {pod_id} 종료 요청 성공")
                            
                            # 종료 확인을 위해 잠시 대기 후 상태 확인
                            await asyncio.sleep(3)
                            final_status = await self._verify_termination(pod_id)
                            
                            if final_status:
                                logger.info(f"✅ RunPod {pod_id} 완전 종료 확인됨")
                                return True
                            else:
                                logger.warning(f"⚠️ RunPod {pod_id} 종료 요청은 성공했으나 상태 확인 실패")
                                return result  # 일단 API 응답을 믿고 True 반환
                        else:
                            logger.error(f"❌ RunPod {pod_id} 종료 요청 실패: {data}")
                            return False
                            
                    except Exception as json_error:
                        logger.error(f"RunPod 응답 JSON 파싱 실패: {json_error} - 원본: {response_text}")
                        return False
                    
        except asyncio.TimeoutError:
            logger.error(f"RunPod {pod_id} 종료 API 타임아웃")
            return False
        except Exception as e:
            logger.error(f"RunPod {pod_id} 종료 중 예외 발생: {e}")
            return False
    
    async def _verify_termination(self, pod_id: str) -> bool:
        """Pod 종료 확인"""
        try:
            status = await self.get_pod_status(pod_id)
            
            # STOPPED, TERMINATED 등의 상태면 성공
            terminated_states = ["STOPPED", "TERMINATED", "TERMINATING"]
            is_terminated = status.status in terminated_states
            
            logger.info(f"Pod {pod_id} 종료 확인: 상태={status.status}, 종료됨={is_terminated}")
            return is_terminated
            
        except Exception as e:
            logger.warning(f"Pod {pod_id} 종료 확인 중 오류: {e}")
            return False  # 확인 실패는 종료 실패로 간주하지 않음
    
    async def wait_for_ready(self, pod_id: str, max_wait_time: int = 300) -> bool:
        """Pod가 시작되고 ComfyUI가 준비될 때까지 대기"""
        
        check_interval = 15  # 15초마다 확인 (시작 시간 고려)
        checks = max_wait_time // check_interval
        
        for i in range(checks):
            try:
                status = await self.get_pod_status(pod_id)
                logger.info(f"Pod {pod_id} 상태 확인 #{i+1}: {status.status}")
                
                if status.status == "RUNNING" and status.endpoint_url:
                    logger.info(f"Pod {pod_id} 실행 중, ComfyUI 연결 확인...")
                    # ComfyUI API 응답 확인
                    if await self._check_comfyui_ready(status.endpoint_url):
                        logger.info(f"✅ Pod {pod_id} 및 ComfyUI 준비 완료!")
                        return True
                    else:
                        logger.info(f"Pod {pod_id} 실행 중이지만 ComfyUI 아직 준비 안됨")
                
                elif status.status in ["FAILED", "TERMINATED", "STOPPED"]:
                    logger.error(f"❌ Pod {pod_id} 실패 상태: {status.status}")
                    return False
                
                elif status.status in ["STARTING", "CREATED"]:
                    logger.info(f"🔄 Pod {pod_id} 시작 중... ({status.status})")
                
                else:
                    logger.info(f"🔄 Pod {pod_id} 상태: {status.status}, 계속 대기...")
                
            except Exception as e:
                logger.warning(f"Pod {pod_id} 상태 확인 중 오류: {e}")
            
            await asyncio.sleep(check_interval)
        
        logger.error(f"❌ Pod {pod_id} 준비 대기 시간 초과 ({max_wait_time}초)")
        return False
    
    async def _check_comfyui_ready(self, endpoint_url: str) -> bool:
        """ComfyUI API 준비 상태 확인"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{endpoint_url}/history",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except:
            return False
    
    
    async def _check_gpu_availability(self) -> dict:
        """GPU 가용성 확인"""
        
        # RunPod GPU 타입 조회 쿼리 (stockStatus 필드는 존재하지 않으므로 제거)
        query = """
        query {
            gpuTypes {
                id
                displayName
                memoryInGb
                secureCloud
                communityCloud
                lowestPrice(input: {gpuCount: 1}) {
                    minimumBidPrice
                    uninterruptablePrice
                }
            }
        }
        """
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            async with aiohttp.ClientSession() as session:
                payload = {"query": query}
                
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"GPU 가용성 조회 실패: {response.status}")
                        logger.error(f"응답 내용: {response_text}")
                        return {}
                    
                    data = await response.json()
                    gpu_types = data.get("data", {}).get("gpuTypes", [])
                    
                    availability = {}
                    for gpu in gpu_types:
                        display_name = gpu.get("displayName", "")
                        lowest_price = gpu.get("lowestPrice", {})
                        
                        # 가격 정보가 있으면 가용하다고 판단
                        min_bid_price = lowest_price.get("minimumBidPrice")
                        uninterruptable_price = lowest_price.get("uninterruptablePrice", 0)
                        
                        has_price = (
                            (min_bid_price is not None and min_bid_price > 0) or 
                            (uninterruptable_price is not None and uninterruptable_price > 0)
                        )
                        
                        # GPU 타입별 확인 (우선순위 순)
                        if "RTX 4090" in display_name or "4090" in display_name:
                            availability["RTX_4090"] = has_price
                        elif "RTX A6000" in display_name or "A6000" in display_name:
                            availability["RTX_A6000"] = has_price
                        elif "RTX A5000" in display_name or "A5000" in display_name:
                            availability["RTX_A5000"] = has_price
                        elif "A40" in display_name:
                            availability["RTX_A40"] = has_price
                    
                    logger.info(f"GPU 가용성: {availability}")
                    return availability
                    
        except Exception as e:
            logger.error(f"GPU 가용성 조회 중 오류: {e}")
            return {}
    
    


# 싱글톤 패턴
_runpod_service_instance = None

def get_runpod_service() -> RunPodService:
    """RunPod 서비스 인스턴스 반환"""
    global _runpod_service_instance
    if _runpod_service_instance is None:
        _runpod_service_instance = RunPodService()
    return _runpod_service_instance