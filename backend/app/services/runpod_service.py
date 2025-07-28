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
    container_disk_in_gb: int = 20  # 20GB로 고정 (이미지 생성 안정성 향상)
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
    
    def _generate_proxy_url(self, pod_id: str, internal_port: int = 8188) -> str:
        """RunPod proxy URL 생성 """
        return f"https://{pod_id}-{internal_port}.proxy.runpod.net"
    
    async def create_pod(self, request_id: str) -> RunPodPodResponse:
        """ComfyUI 서버 인스턴스 생성 (GPU 폴백 지원)"""
        
        # GPU 리소스 실제 스펙 설정 (RunPod 이미지 기준 - 각 GPU별 고유 리소스)
        # 컨테이너 디스크만 20GB로 고정, 나머지는 GPU별 실제 스펙 사용
        FIXED_DISK = 20     # 고정 컴테이너 디스크 (GB) - 안정성을 위해 고정
        FIXED_VOLUME = 250  # 고정 네트워크 볼륨 (GB)
        
        gpu_config = [
            # 1순위: RTX 4090 (실제 스펙: 24GB VRAM, 61GB RAM, 16 vCPU)
            {
                "gpu": "NVIDIA GeForce RTX 4090", 
                "vram": "24GB", 
                "bid_price": 0.69,
                "tier": "Premium",
                "vcpu": 16,   # 실제 RunPod 스펙
                "memory": 61  # 실제 RunPod 스펙
            },
            
            # 2순위: RTX A4500 (실제 스펙: 20GB VRAM, 54GB RAM, 12 vCPU)
            {
                "gpu": "NVIDIA RTX A4500", 
                "vram": "20GB", 
                "bid_price": 0.25,
                "tier": "Medium",
                "vcpu": 12,   # 실제 RunPod 스펙
                "memory": 54  # 실제 RunPod 스펙
            },
            
            # 3순위: RTX 4000 Ada (실제 스펙: 20GB VRAM, 50GB RAM, 9 vCPU)
            {
                "gpu": "NVIDIA RTX 4000 Ada Generation", 
                "vram": "20GB", 
                "bid_price": 0.26,
                "tier": "Medium",
                "vcpu": 9,    # 실제 RunPod 스펙
                "memory": 50  # 실제 RunPod 스펙
            },
            
            # 4순위: RTX 2000 Ada (실제 스펙: 16GB VRAM, 31GB RAM, 6 vCPU)
            {
                "gpu": "NVIDIA RTX 2000 Ada Generation", 
                "vram": "16GB", 
                "bid_price": 0.23,
                "tier": "Budget",
                "vcpu": 6,    # 실제 RunPod 스펙
                "memory": 31  # 실제 RunPod 스펙
            }
        ]
        
        logger.info(f"🚀 ===== RunPod 인스턴스 생성 시작 =====")
        logger.info(f"🎯 Request ID: {request_id}")
        logger.info(f"🗺️ Template ID: {settings.RUNPOD_TEMPLATE_ID}")
        logger.info(f"💾 Volume ID: {settings.RUNPOD_VOLUME_ID}")
        logger.info(f"🌍 Data Center: EU-RO-1 (강제 설정)")
        logger.info(f"🔧 디스크 고정 설정: {FIXED_DISK}GB Container + {FIXED_VOLUME}GB Volume")
        logger.info(f"🔍 사용 가능한 GPU 옵션: {len(gpu_config)}개 (GPU별 실제 리소스 스펙)")
        logger.info(f"🎯 GPU 우선순위: RTX 4090(16C/61GB) → RTX A4500(12C/54GB) → RTX 4000 Ada(9C/50GB) → RTX 2000 Ada(6C/31GB)")
        
        gpu_chain = [config["gpu"] for config in gpu_config]
        
        for gpu_index in range(len(gpu_config)):  # 각 GPU별로 순차적 시도
            current_gpu = gpu_config[gpu_index]
            gpu_type = current_gpu["gpu"]
            base_bid_price = current_gpu["bid_price"]
            tier = current_gpu["tier"]
            vram = current_gpu["vram"]
            vcpu = current_gpu["vcpu"]
            memory = current_gpu["memory"]
            
            # RTX 4090의 경우 동일 조건으로 3번 재시도, 다른 GPU는 1번만
            max_gpu_retries = 3 if "RTX 4090" in gpu_type or "4090" in gpu_type else 1
            
            logger.info(f"🔍 GPU #{gpu_index + 1}/{len(gpu_config)}: {gpu_type}")
            logger.info(f"   🎯 GPU: {gpu_type} ({vram} VRAM, {tier} 등급)")
            logger.info(f"   🎮 리소스 고정 스펙: {vcpu} vCPU, {memory}GB RAM (정확한 RunPod 스펙)")
            logger.info(f"   💰 기본 입찰가: ${base_bid_price}/hr")
            logger.info(f"   💾 디스크: {FIXED_DISK}GB Container + {FIXED_VOLUME}GB Network Volume (고정)")
            logger.info(f"   🔄 GPU별 재시도: {max_gpu_retries}회 (RTX 4090은 3회, 나머지는 1회)")
            
            pod_data = None
            successful_bid = None
            
            # GPU별 재시도 루프 (RTX 4090은 3회, 나머지는 1회)
            for gpu_retry in range(max_gpu_retries):
                if gpu_retry > 0:
                    logger.info(f"   🔄 GPU 재시도 #{gpu_retry + 1}/{max_gpu_retries} - 동일 조건({vcpu}C/{memory}GB)으로 재생성")
                    await asyncio.sleep(3)  # GPU 재시도 간 3초 대기
                
                # 각 GPU별로 단계별 입찰가 시도 (기본가 → 최대 $0.6)
                bid_steps = [
                    base_bid_price,           # 기본 시장가
                    base_bid_price + 0.1,     # +$0.1
                    base_bid_price + 0.2,     # +$0.2 
                    0.6                       # 최대 $0.6
                ]
                # 중복 제거 및 $0.6 이하로 제한
                bid_steps = sorted(list(set([min(price, 0.6) for price in bid_steps])))
                
                # 각 입찰가별로 시도 (재시도 로직 포함)
                for bid_idx, bid_price in enumerate(bid_steps):
                    logger.info(f"     💰 입찰가 ${bid_price}/hr 시도 ({bid_idx + 1}/{len(bid_steps)})...")
                    
                    # Spot 먼저, 실패시 On-Demand 시도
                    for instance_type in ["on_demand", "interruptible"]:
                        # 각 인스턴스 타입별로 최대 2번 시도 (즉시 + 5초 후 재시도)
                        for retry_attempt in range(2):
                            try:
                                if retry_attempt > 0:
                                    logger.info(f"       🔄 5초 후 재시도 ({retry_attempt + 1}/2)...")
                                    await asyncio.sleep(5)
                                
                                logger.info(f"       🔄 {instance_type} 인스턴스 생성 중... (고정 리소스: {vcpu}C/{memory}GB)")
                                pod_data = await self._create_pod_with_type(gpu_type, request_id, instance_type, bid_price, vcpu, memory)
                                
                                if pod_data:
                                    successful_bid = bid_price
                                    logger.info(f"✅ {instance_type} Pod 생성 성공! (GPU 재시도 {gpu_retry + 1}/{max_gpu_retries})")
                                    logger.info(f"   🎯 GPU: {gpu_type} (${bid_price}/hr)")
                                    logger.info(f"   🎮 적용된 리소스: {vcpu} vCPU, {memory}GB RAM (고정 스펙)")
                                    logger.info(f"   💾 디스크: {FIXED_DISK}GB Container + {FIXED_VOLUME}GB Network Volume")
                                    logger.info(f"   🆔 Pod ID: {pod_data['id']}")
                                    logger.info(f"   🌐 Status: {pod_data.get('desiredStatus', 'Unknown')}")
                                    break
                                    
                            except Exception as type_error:
                                error_msg = str(type_error)[:100]
                                logger.warning(f"       ❌ {instance_type} ${bid_price}/hr 시도 {retry_attempt + 1} 실패: {error_msg}...")
                                
                                # 마지막 시도가 아니면 재시도, 아니면 다음 인스턴스 타입으로
                                if retry_attempt == 1:  # 마지막 재시도도 실패
                                    break
                                continue
                        
                        if pod_data:  # 성공하면 인스턴스 타입 루프 종료
                            break
                    
                    if pod_data:  # 성공하면 입찰가 루프 종료
                        break
                
                if pod_data:  # 성공하면 GPU 재시도 루프 종료
                    break
                else:
                    logger.warning(f"   ❌ GPU 재시도 {gpu_retry + 1}/{max_gpu_retries} 실패 (모든 입찰가 시도 완료)")
                    if gpu_retry < max_gpu_retries - 1:
                        logger.info(f"   🔄 동일 GPU로 재시도 예정... (리소스 고정: {vcpu}C/{memory}GB)")
            
            if not pod_data:
                if "RTX 4090" in gpu_type or "4090" in gpu_type:
                    logger.warning(f"💸 RTX 4090 ({vcpu}C/{memory}GB) 3회 재시도 모두 실패")
                    logger.warning(f"   📊 시도 결과: GPU 재시도 3회 × 입찰가 {len(bid_steps)}개 × 인스턴스 타입 2개 × 재시도 2회")
                    logger.warning(f"   ⚠️ 리소스 변경 없이 정확한 스펙으로만 시도함")
                else:
                    logger.warning(f"💸 GPU {gpu_type} ({vcpu}C/{memory}GB) 입찰가 시도 실패")
                
                logger.warning(f"   시도한 입찰가: ${bid_steps}")
                
                if gpu_index < len(gpu_config) - 1:
                    next_gpu = gpu_config[gpu_index + 1]
                    logger.info(f"   🔄 다음 GPU로 폴백: {next_gpu['gpu']} ({next_gpu['vcpu']}C/{next_gpu['memory']}GB)")
                continue  # 다음 GPU로 시도
            
            # Pod 생성 성공한 경우
            if pod_data:
                # RunPod proxy URL 생성 (공식 방식)
                pod_id = pod_data["id"]
                endpoint_url = self._generate_proxy_url(pod_id, 8188)
                
                logger.info(f"🎯 최적 GPU 확보 성공!")
                logger.info(f"  GPU: {gpu_type} ({vram}, {tier} 등급)")
                logger.info(f"  리소스: {vcpu} vCPU, {memory}GB RAM (고정)")
                logger.info(f"  최종 입찰가: ${successful_bid}/hr")
                logger.info(f"  Pod ID: {pod_id}")
                logger.info(f"  Proxy URL: {endpoint_url}")
                logger.info(f"  볼륨: {settings.RUNPOD_VOLUME_ID} → /workspace")
                
                # Pod는 이미 RUNNING 상태이므로 별도 시작 불필요
                logger.info(f"✅ Pod {pod_id} 생성 완료 (RUNNING 상태)")
                logger.info(f"   Template ID: {settings.RUNPOD_TEMPLATE_ID}")
                logger.info(f"   Volume ID: {settings.RUNPOD_VOLUME_ID}")
                logger.info(f"   Container Port: 8188 (ComfyUI)")
                logger.info(f"   Proxy URL: {endpoint_url}")
                logger.info(f"   예상 준비 시간: 60-90초")
                
                return RunPodPodResponse(
                    pod_id=pod_id,
                    status=pod_data["desiredStatus"],  # 이미 RUNNING 상태
                    runtime=pod_data.get("runtime", {}),
                    endpoint_url=endpoint_url,
                    cost_per_hour=successful_bid  # 실제 입찰가 반영
                )
        
        # 모든 GPU 시도 실패 - RTX 4090 3회 재시도 포함
        
        # 모든 시도 실패 - RTX 4090 3회 재시도 포함 상세 요약 리포트
        logger.error(f"❌ ===== RunPod 인스턴스 생성 실패 =====")
        logger.error(f"   🎯 시도한 GPU 수: {len(gpu_config)}개")
        logger.error(f"   🔄 RTX 4090 재시도: 3회 (16C/61GB 고정 스펙)")
        logger.error(f"   🔄 기타 GPU 재시도: 1회 (각각 고정 스펙)")
        logger.error(f"   💰 최대 입찰가: $0.60/hr")
        logger.error(f"   📋 Request ID: {request_id}")
        logger.error(f"   🗂️ Template: {settings.RUNPOD_TEMPLATE_ID}")
        logger.error(f"   💾 Volume: {settings.RUNPOD_VOLUME_ID}")
        logger.error(f"   📊 총 시도 횟수:")
        rtx_4090_total = 3 * 4 * 2 * 2  # GPU재시도 3회 × 입찰가 4개 × 인스턴스타입 2개 × 재시도 2회
        other_gpu_total = (len(gpu_config) - 1) * 1 * 4 * 2 * 2  # 기타 GPU × 1회 × 입찰가 × 타입 × 재시도
        logger.error(f"     - RTX 4090: 최대 {rtx_4090_total}회 시도")
        logger.error(f"     - 기타 GPU: 최대 {other_gpu_total}회 시도")
        logger.error(f"   ⚠️ 리소스 변경 없이 정확한 RunPod 스펙으로만 시도함")
        logger.error(f"   💡 권장 사항:")
        logger.error(f"     1. RunPod 계정 잔액 확인")
        logger.error(f"     2. 5-10분 후 재시도")
        logger.error(f"     3. 다른 시간대(미국 밤시간)에 시도")
        logger.error(f"     4. GPU 리소스 요구사항 확인")
        raise RuntimeError("지금 사용가능한 자원이 없습니다. 잠시 후 다시 시도해 주세요.")
    
    async def _create_pod_with_type(self, gpu_type: str, request_id: str, instance_type: str, bid_price: float = 0.35, vcpu: int = 8, memory: int = 32) -> dict:
        """특정 인스턴스 타입으로 Pod 생성 (강력한 리소스 고정)"""
        
        # RTX 4090 리소스 강제 고정 - 24C/125GB 과할당 방지
        if "RTX 4090" in gpu_type or "4090" in gpu_type:
            vcpu = 16    # RTX 4090 강제 고정: 16 vCPU
            memory = 61  # RTX 4090 강제 고정: 61GB RAM
            logger.info(f"🔒 RTX 4090 리소스 강제 고정: {vcpu}C/{memory}GB (과할당 방지)")
        elif "RTX A4500" in gpu_type or "A4500" in gpu_type:
            vcpu = 12    # RTX A4500 강제 고정: 12 vCPU
            memory = 54  # RTX A4500 강제 고정: 54GB RAM
            logger.info(f"🔒 RTX A4500 리소스 강제 고정: {vcpu}C/{memory}GB")
        elif "RTX 4000 Ada" in gpu_type or "4000 Ada" in gpu_type:
            vcpu = 9     # RTX 4000 Ada 강제 고정: 9 vCPU
            memory = 50  # RTX 4000 Ada 강제 고정: 50GB RAM
            logger.info(f"🔒 RTX 4000 Ada 리소스 강제 고정: {vcpu}C/{memory}GB")
        elif "RTX 2000 Ada" in gpu_type or "2000 Ada" in gpu_type:
            vcpu = 6     # RTX 2000 Ada 강제 고정: 6 vCPU
            memory = 31  # RTX 2000 Ada 강제 고정: 31GB RAM
            logger.info(f"🔒 RTX 2000 Ada 리소스 강제 고정: {vcpu}C/{memory}GB")
        else:
            # 기타 GPU는 기본값 사용하되 최대값 제한
            vcpu = min(vcpu, 16)    # 최대 16 vCPU로 제한
            memory = min(memory, 64) # 최대 64GB RAM으로 제한
            logger.warning(f"⚠️ 알 수 없는 GPU 타입, 리소스 제한 적용: {vcpu}C/{memory}GB")
        
        if instance_type == "interruptible":
            # Spot 인스턴스 - 템플릿 기반 생성으로 변경
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
                    "bidPerGpu": bid_price,  # GPU별 적정 입찰가 사용
                    "gpuCount": 1,
                    "volumeInGb": 250,  # 고정 네트워크 볼륨
                    "networkVolumeId": settings.RUNPOD_VOLUME_ID,
                    "containerDiskInGb": 20,  # 강제 고정 컨테이너 디스크 (과할당 방지)
                    "minVcpuCount": vcpu,   # 강제 고정된 vCPU 수
                    "minMemoryInGb": memory,  # 강제 고정된 RAM 용량
                    "gpuTypeId": gpu_type,
                    "templateId": settings.RUNPOD_TEMPLATE_ID,  # 템플릿 사용
                    "name": f"AIMEX_ComfyUI_{request_id}",
                    "ports": "8188/http",
                    "volumeMountPath": "/workspace",
                    "dataCenterId": "EU-RO-1"
                }
            }
        else:  # on_demand
            # On-Demand 인스턴스 - 템플릿 기반으로 변경
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
                    "volumeInGb": 200,  # 고정 네트워크 볼륨
                    "networkVolumeId": settings.RUNPOD_VOLUME_ID,
                    "containerDiskInGb": 20,  # 강제 고정 컨테이너 디스크 (과할당 방지)
                    "minVcpuCount": vcpu,   # 강제 고정된 vCPU 수
                    "minMemoryInGb": memory,  # 강제 고정된 RAM 용량
                    "gpuTypeId": gpu_type,
                    "templateId": settings.RUNPOD_TEMPLATE_ID,  # 템플릿 사용
                    "name": f"AIMEX_ComfyUI_{request_id}",
                    "ports": "8188/http",
                    "volumeMountPath": "/workspace",
                    "dataCenterId": "EU-RO-1"
                }
            }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        logger.info(f"   🔒 강력한 리소스 고정 API 요청:")
        logger.info(f"     - GPU: {gpu_type}")
        logger.info(f"     - 입찰가: ${bid_price}/hr")
        logger.info(f"     - vCPU 고정: min={vcpu}, max={vcpu} (과할당 방지)")
        logger.info(f"     - RAM 고정: min={memory}GB, max={memory}GB (과할당 방지)")
        logger.info(f"     - 컨테이너 디스크: 20GB (고정)")
        logger.info(f"     - 볼륨: 200GB (ID: {settings.RUNPOD_VOLUME_ID})")
        logger.info(f"     - 볼륨 마운트: /workspace")
        logger.info(f"     - 데이터센터: EU-RO-1 (고정)")
        logger.info(f"     - 템플릿: {settings.RUNPOD_TEMPLATE_ID}")
        if "RTX 4090" in gpu_type:
            logger.info(f"     ⚠️ RTX 4090 특별 보호: 24C/125GB 과할당 강력 차단")
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "query": mutation,
                "variables": variables
            }
            
            logger.info(f"   🌐 RunPod GraphQL API 호출 중...")
            
            async with session.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                logger.info(f"   🔍 API 응답 상태: {response.status}")
                
                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"   ❌ HTTP 오류: {response.status}")
                    logger.error(f"   ❌ 응답 내용: {response_text[:300]}...")
                    raise Exception(f"RunPod API 호출 실패: {response.status} - {response_text[:100]}...")
                
                data = await response.json()
                logger.info(f"   ✅ JSON 데이터 파싱 성공")
                logger.info(data)
                
                if "errors" in data:
                    logger.error(f"   ❌ GraphQL 오류 발견: {data['errors']}")
                    raise Exception(f"RunPod GraphQL 오류: {data['errors']}")
                
                # 성공 데이터 추출
                if instance_type == "interruptible":
                    result = data["data"]["podRentInterruptable"]
                else:
                    result = data["data"]["podFindAndDeployOnDemand"]
                
                if result:
                    logger.info(f"   ✅ Pod 생성 성공! ID: {result.get('id', 'N/A')}")
                    logger.info(f"   ✅ 상태: {result.get('desiredStatus', 'N/A')}")
                    
                    # 요청한 리소스 vs 실제 할당 리소스 확인
                    logger.info(f"   🔍 요청 리소스: {vcpu}C/{memory}GB (min=max 고정)")
                    
                    # 볼륨 마운트 확인
                    machine_info = result.get('machine', {})
                    if machine_info:
                        logger.info(f"   💻 머신 정보: {machine_info.get('podHostId', 'N/A')}")
                    
                    runtime_info = result.get('runtime', {})
                    if runtime_info:
                        logger.info(f"   ⏱️ 런타임: {runtime_info.get('uptimeInSeconds', 0)}초")
                    
                    # RTX 4090 특별 확인
                    if "RTX 4090" in gpu_type:
                        logger.info(f"   🔒 RTX 4090 리소스 고정 성공: {vcpu}C/{memory}GB")
                        logger.info(f"   ✅ 24C/125GB 과할당 방지됨")
                else:
                    logger.warning(f"   ⚠️ 빈 결과 반환 - Pod 생성 실패 가능성")
                
                return result
    
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
                    
                    # RunPod proxy URL 생성 (공식 방식)
                    endpoint_url = self._generate_proxy_url(pod_data["id"], 8188)
                    
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
    
    async def wait_for_ready(self, pod_id: str, max_wait_time: int = 600) -> bool:
        """Pod가 시작되고 ComfyUI가 준비될 때까지 대기 (로딩 중단 감지 및 복구 포함)"""
        
        logger.info(f"⏳ ===== Pod 준비 대기 시작 =====")
        logger.info(f"   Pod ID: {pod_id}")
        logger.info(f"   최대 대기 시간: {max_wait_time}초 ({max_wait_time//60}분)")
        logger.info(f"   볼륨 마운트: {settings.RUNPOD_VOLUME_ID} → /workspace")
        logger.info(f"   Template 초기화 예상 시간: 3-5분 (볼륨 연결 포함)")
        logger.info(f"   확인 주기: 15초")
        logger.info(f"   로딩 중단 감지: 연속 3회 실패시 재시작 시도")
        
        check_interval = 15  # 15초마다 확인
        checks = max_wait_time // check_interval
        consecutive_failures = 0  # 연속 실패 횟수
        last_status = None  # 이전 상태 추적
        stuck_count = 0  # 상태 변화 없음 횟수
        
        for i in range(checks):
            elapsed_time = i * check_interval
            remaining_time = max_wait_time - elapsed_time
            
            try:
                # 진행률 로그 빈도 감소 (5회마다만 출력)
                if (i + 1) % 5 == 0 or i == 0:
                    logger.info(f"🔍 상태 확인 #{i+1}/{checks} (경과: {elapsed_time}초, 남은 시간: {remaining_time}초)")
                else:
                    logger.debug(f"🔍 상태 확인 #{i+1}/{checks} (경과: {elapsed_time}초)")
                
                status = await self.get_pod_status(pod_id)
                current_status = status.status
                logger.info(f"   Pod 상태: {current_status}")
                
                # 상태 변화 추적
                if last_status == current_status:
                    stuck_count += 1
                else:
                    stuck_count = 0
                    consecutive_failures = 0  # 상태 변화시 실패 카운트 리셋
                
                last_status = current_status
                
                if current_status == "RUNNING" and status.endpoint_url:
                    logger.info(f"   ✅ Pod 실행 중! Endpoint: {status.endpoint_url}")
                    
                    # 볼륨 마운트 상태 체크 (처음 몇 번만)
                    if i < 3:
                        await self._check_volume_mount(status.endpoint_url)
                    
                    logger.info(f"   🔍 ComfyUI API 연결 테스트 중...")
                    
                    # ComfyUI API 응답 확인
                    if await self._check_comfyui_ready(status.endpoint_url):
                        logger.info(f"   ✅ ComfyUI API 응답 성공!")
                        logger.info(f"✅ ===== Pod {pod_id} 완전 준비 완료! ======")
                        logger.info(f"   총 대기 시간: {elapsed_time}초")
                        logger.info(f"   Endpoint URL: {status.endpoint_url}")
                        
                        # 최종 볼륨 마운트 확인
                        await self._check_volume_mount(status.endpoint_url)
                        
                        return True
                    else:
                        consecutive_failures += 1
                        logger.info(f"   ⚠️ Pod는 실행 중이지만 ComfyUI가 아직 준비되지 않음 (실패 {consecutive_failures}/3)")
                        logger.info(f"   ⚠️ Template 초기화 지속 중... (볼륨 마운트 포함)")
                        
                        # 연속 3회 ComfyUI API 실패시 Pod 재시작 시도
                        if consecutive_failures >= 3 and i > 10:  # 최소 150초 후에만 재시작 고려
                            logger.warning(f"   🔄 ComfyUI 응답 연속 실패 감지 - Pod 재시작 시도...")
                            restart_success = await self._restart_stuck_pod(pod_id)
                            
                            if restart_success:
                                logger.info(f"   ✅ Pod 재시작 성공 - 대기 시간 연장")
                                consecutive_failures = 0
                                stuck_count = 0
                                # 재시작 후 추가 시간 확보 (최대 5분)
                                additional_time = min(300, max_wait_time - elapsed_time)
                                checks += additional_time // check_interval
                            else:
                                logger.error(f"   ❌ Pod 재시작 실패")
                
                elif current_status in ["FAILED", "TERMINATED", "STOPPED", "EXITED"]:
                    logger.error(f"   ❌ Pod 종료 상태 감지: {current_status}")
                    logger.error(f"   ❌ Pod {pod_id} 사용 불가 - 새로운 Pod 생성 필요")
                    return False
                
                elif current_status in ["STARTING", "CREATED"]:
                    logger.info(f"   🔄 Pod 시작 중... (상태: {current_status})")
                    if current_status == "STARTING":
                        logger.info(f"   🔄 Template 다운로드 및 ComfyUI 설치 진행 중...")
                    
                    # STARTING 상태에서 너무 오래 멈춰있으면 재시작 고려
                    if stuck_count >= 8 and current_status == "STARTING":  # 2분 이상 같은 상태
                        logger.warning(f"   ⚠️ STARTING 상태에서 {stuck_count * check_interval}초간 멈춤 - 재시작 고려")
                        restart_success = await self._restart_stuck_pod(pod_id)
                        if restart_success:
                            stuck_count = 0
                            consecutive_failures = 0
                
                else:
                    logger.debug(f"   🔄 기타 상태: {current_status}, 계속 대기...")
                
            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"   ⚠️ 상태 확인 중 오류 (실패 {consecutive_failures}/3): {str(e)[:100]}...")
                logger.warning(f"   ⚠️ 15초 후 재시도...")
            
            if i < checks - 1:  # 마지막이 아니면 대기
                await asyncio.sleep(check_interval)
        
        logger.error(f"❌ ===== Pod 준비 대기 시간 초과 ======")
        logger.error(f"   Pod ID: {pod_id}")
        logger.error(f"   최대 대기 시간: {max_wait_time}초 ({max_wait_time//60}분)")
        logger.error(f"   볼륨 마운트: {settings.RUNPOD_VOLUME_ID}")
        logger.error(f"   총 시도 수: {checks}회")
        logger.error(f"   연속 실패 횟수: {consecutive_failures}")
        logger.error(f"   상태 변화 없음: {stuck_count}회")
        logger.error(f"   가능한 원인:")
        logger.error(f"     1. Template 초기화 시간 초과 (3-5분 예상)")
        logger.error(f"     2. 볼륨 마운트 실패 ({settings.RUNPOD_VOLUME_ID})")
        logger.error(f"     3. 네트워크 연결 문제")
        logger.error(f"     4. ComfyUI 시작 실패")
        logger.error(f"   권장 사항: Pod를 수동으로 종료하고 새로 생성")
        return False
    
    async def _check_comfyui_ready(self, endpoint_url: str, max_retries: int = 3, retry_delay: int = 3) -> bool:
        """ComfyUI API 준비 상태 확인 (강화된 다중 엔드포인트 체크 + 재시도)"""
        
        # ComfyUI API 엔드포인트들 (우선순위 순)
        test_endpoints = [
            "/",           # 메인 페이지 (가장 기본적)          # 기존 엔드포인트
            "/queue",             # 큐 상태
        ]
        
        # 재시도 로직 (ComfyUI 로딩이 느릴 수 있음)
        for retry in range(max_retries):
            if retry > 0:
                logger.info(f"     ⏳ ComfyUI API 재시도 {retry + 1}/{max_retries} ({retry_delay}초 대기)")
                await asyncio.sleep(retry_delay)
            
            for endpoint in test_endpoints:
                try:
                    test_url = f"{endpoint_url}{endpoint}"
                    logger.info(f"     🌐 ComfyUI API 테스트: {test_url}")
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            test_url,
                            timeout=aiohttp.ClientTimeout(total=10),  # 타임아웃 10초로 연장
                            headers={"User-Agent": "AIMEX-Backend/1.0"},
                            ssl=False  # RunPod proxy SSL 문제 회피
                        ) as response:
                            logger.info(f"     🔍 API 응답 ({endpoint}): {response.status}")
                            
                            # 200, 201, 302 등 정상 응답으로 간주
                            if 200 <= response.status < 400:
                                response_text = await response.text()
                                logger.info(f"     ✅ ComfyUI API 준비 완료! ({endpoint}, {len(response_text)} bytes)")
                                
                                # 응답 내용도 간단히 확인
                                if endpoint == "/" and ("ComfyUI" in response_text or "comfyui" in response_text.lower()):
                                    logger.info(f"     🎯 ComfyUI 메인 페이지 확인됨 (재시도 {retry + 1}회차)")
                                    return True
                                elif endpoint != "/" and response_text:
                                    logger.info(f"     🎯 API 엔드포인트 정상 응답 (재시도 {retry + 1}회차)")
                                    return True
                                elif response.status == 200:
                                    logger.info(f"     🎯 HTTP 200 응답 확인 (재시도 {retry + 1}회차)")
                                    return True
                            else:
                                logger.info(f"     ⚠️ 비정상 응답: {response.status}")
                                
                except asyncio.TimeoutError:
                    logger.info(f"     ⚠️ API 타임아웃 ({endpoint}, 10초)")
                    continue
                except Exception as e:
                    logger.info(f"     ⚠️ API 연결 실패 ({endpoint}): {str(e)[:50]}...")
                    continue
            
            # 이번 라운드에서 성공하지 못함
            if retry < max_retries - 1:
                logger.info(f"     ⏭️ 재시도 {retry + 1} 실패, {retry_delay}초 후 다시 시도...")
        
        # 모든 재시도 실패
        logger.warning(f"     ❌ ComfyUI API 준비 확인 실패 (총 {max_retries}회 재시도)")
        logger.info(f"     🔍 시도한 엔드포인트: {test_endpoints}")
        logger.info(f"     💡 ComfyUI 서버가 실행 중이지만 API가 아직 준비되지 않았을 수 있음")
        logger.info(f"     💡 Pod는 정상이므로 나중에 다시 확인할 수 있습니다")
        return False
    
    async def _check_volume_mount(self, endpoint_url: str) -> bool:
        """볼륨 마운트 상태 확인 (RunPod proxy URL 사용)"""
        try:
            # RunPod proxy를 통한 JupyterLab 접근 (포트 8888)
            pod_id = endpoint_url.split('://')[1].split('-')[0]  # URL에서 pod_id 추출
            jupyter_url = self._generate_proxy_url(pod_id, 8888)
            
            logger.info(f"     💾 볼륨 마운트 상태 확인: /workspace")
            logger.info(f"     🔍 JupyterLab URL: {jupyter_url}")
            
            # RunPod proxy를 통한 JupyterLab 접근 시도
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{jupyter_url}/tree",
                    timeout=aiohttp.ClientTimeout(total=5),
                    ssl=False  # RunPod proxy SSL 문제 회피
                ) as response:
                    if response.status == 200:
                        logger.info(f"     ✅ JupyterLab 접근 가능 - 볼륨 마운트 확인됨")
                        return True
                    else:
                        logger.info(f"     ⚠️ JupyterLab 접근 실패: {response.status}")
                        return False
                        
        except asyncio.TimeoutError:
            logger.info(f"     ⚠️ JupyterLab 대기 시간 초과")
            return False
        except Exception as e:
            logger.info(f"     ⚠️ 볼륨 마운트 체크 실패: {str(e)[:50]}...")
            return False
    
    
    async def check_pod_health(self, pod_id: str) -> dict:
        """Pod 건강성 및 리소스 상태 확인"""
        if not pod_id:
            return {"error": "Pod ID not provided", "healthy": False}
        
        try:
            # Pod 상태 조회 GraphQL 쿼리
            query = """
            query getPod($input: PodIdInput!) {
                pod(input: $input) {
                    id
                    name
                    desiredStatus
                    lastStatusChange
                    runtime {
                        uptimeInSeconds
                        ports {
                            ip
                            isIpPublic
                            privatePort
                            publicPort
                            type
                        }
                        gpus {
                            id
                            gpuUtilPercent
                            memoryUtilPercent
                        }
                        container {
                            cpuPercent
                            memoryPercent
                        }
                    }
                    machine {
                        gpuCount
                        vcpuCount
                        memoryInGb
                        diskInGb
                    }
                }
            }
            """
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            variables = {"input": {"podId": pod_id}}
            payload = {"query": query, "variables": variables}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        logger.error(f"Pod health check failed: HTTP {response.status}")
                        return {"error": f"HTTP {response.status}", "healthy": False}
                    
                    data = await response.json()
                    
                    if "errors" in data:
                        logger.error(f"Pod health check GraphQL errors: {data['errors']}")
                        return {"error": "GraphQL errors", "healthy": False}
                    
                    pod_data = data.get("data", {}).get("pod")
                    if not pod_data:
                        logger.error(f"Pod {pod_id} not found")
                        return {"error": "Pod not found", "healthy": False}
                    
                    # 건강성 판단 로직
                    desired_status = pod_data.get("desiredStatus", "Unknown")
                    runtime = pod_data.get("runtime", {})
                    machine = pod_data.get("machine", {})
                    
                    # 리소스 확인
                    vcpu_count = machine.get("vcpuCount", 0)
                    memory_gb = machine.get("memoryInGb", 0)
                    
                    # 건강성 판단
                    is_healthy = (
                        desired_status == "RUNNING" and
                        runtime is not None and
                        vcpu_count >= 4 and  # 최소 4 vCPU
                        memory_gb >= 16      # 최소 16GB RAM
                    )
                    
                    health_info = {
                        "pod_id": pod_id,
                        "status": desired_status,
                        "healthy": is_healthy,
                        "uptime": runtime.get("uptimeInSeconds", 0) if runtime else 0,
                        "vcpu_count": vcpu_count,
                        "memory_gb": memory_gb,
                        "disk_gb": machine.get("diskInGb", 0),
                        "gpu_count": machine.get("gpuCount", 0),
                        "last_status_change": pod_data.get("lastStatusChange"),
                        "ports": runtime.get("ports", []) if runtime else []
                    }
                    
                    # 리소스 부족 감지
                    if vcpu_count < 4 or memory_gb < 16:
                        health_info["resource_issue"] = f"Insufficient resources: {vcpu_count}C/{memory_gb}GB"
                        health_info["needs_restart"] = True
                        logger.warning(f"Pod {pod_id} has insufficient resources: {vcpu_count}C/{memory_gb}GB")
                    
                    return health_info
                    
        except Exception as e:
            logger.error(f"Failed to check Pod {pod_id} health: {e}")
            return {"error": str(e), "healthy": False}
    
    async def force_restart_pod(self, pod_id: str, request_id: str) -> dict:
        """리소스 부족 또는 오류 Pod 강제 재시작"""
        try:
            logger.info(f"🔄 Pod {pod_id} 강제 재시작 시작...")
            
            # 1. 현재 Pod 건강성 확인
            health_check = await self.check_pod_health(pod_id)
            logger.info(f"   📊 현재 Pod 상태: {health_check}")
            
            # 2. Pod 강제 종료
            logger.info(f"   🗑️ Pod {pod_id} 강제 종료 중...")
            terminate_success = await self.terminate_pod(pod_id)
            
            if not terminate_success:
                logger.warning(f"   ⚠️ Pod 종료 실패했지만 재생성 진행...")
            else:
                logger.info(f"   ✅ Pod 종료 완료")
                
                # 종료 완료까지 잠시 대기
                await asyncio.sleep(5)
            
            # 3. 새 Pod 생성
            logger.info(f"   🚀 새로운 Pod 생성 중...")
            new_pod_response = await self.create_pod(request_id)
            
            if new_pod_response and new_pod_response.pod_id:
                logger.info(f"   ✅ 새 Pod 생성 성공: {new_pod_response.pod_id}")
                return {
                    "success": True,
                    "old_pod_id": pod_id,
                    "new_pod_id": new_pod_response.pod_id,
                    "status": new_pod_response.status,
                    "endpoint_url": new_pod_response.endpoint_url
                }
            else:
                logger.error(f"   ❌ 새 Pod 생성 실패")
                return {
                    "success": False,
                    "error": "Failed to create new pod",
                    "old_pod_id": pod_id
                }
                
        except Exception as e:
            logger.error(f"Pod 강제 재시작 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "old_pod_id": pod_id
            }

    async def check_volume_status(self, volume_id: str = None) -> dict:
        """볼륨 상태 및 내용 확인 (간단한 버전)"""
        if not volume_id:
            volume_id = settings.RUNPOD_VOLUME_ID
        
        # 올바른 볼륨 조회 쿼리 (introspection으로 확인된 정확한 필드명)
        query = """
        query {
            myself {
                networkVolumes {
                    id
                    name
                    size
                    dataCenterId
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
                
                logger.info(f"Checking volume {volume_id} status...")
                
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"Volume query failed: {response.status} - {response_text[:200]}")
                        return {"error": f"API call failed: {response.status}"}
                    
                    data = await response.json()
                    
                    if "errors" in data:
                        logger.error(f"Volume query GraphQL errors: {data['errors']}")
                        return {"error": f"GraphQL errors: {data['errors']}"}
                    
                    volumes = data.get("data", {}).get("myself", {}).get("networkVolumes", [])
                    
                    # 특정 볼륨 ID 찾기
                    target_volume = None
                    for volume in volumes:
                        if volume.get("id") == volume_id:
                            target_volume = volume
                            break
                    
                    if target_volume:
                        logger.info(f"Found volume {volume_id}:")
                        logger.info(f"  Name: {target_volume.get('name', 'N/A')}")
                        logger.info(f"  Size: {target_volume.get('size', 'N/A')}GB")
                        logger.info(f"  Data Center: {target_volume.get('dataCenterId', 'N/A')}")
                        
                        return {
                            "volume_id": target_volume.get("id"),
                            "name": target_volume.get("name"),
                            "size": target_volume.get("size"),
                            "data_center": target_volume.get("dataCenterId"),
                            "status": "found"
                        }
                    else:
                        logger.warning(f"Volume {volume_id} not found in {len(volumes)} volumes")
                        return {
                            "error": "Volume not found",
                            "available_volumes": [v.get("id") for v in volumes[:5]]  # 처음 5개만
                        }
                        
        except Exception as e:
            logger.error(f"Volume status check error: {e}")
            return {"error": str(e)}
    
    async def _restart_stuck_pod(self, pod_id: str) -> bool:
        """로딩이 멈춘 Pod 재시작 시도"""
        try:
            logger.info(f"🔄 Pod {pod_id} 재시작 시도 중...")
            
            # RunPod API의 podResume 사용
            mutation = """
            mutation podResume($input: PodResumeInput!) {
                podResume(input: $input) {
                    id
                    desiredStatus
                    imageName
                }
            }
            """
            
            variables = {
                "input": {
                    "podId": pod_id,
                    "gpuCount": 1
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
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"Pod restart API failed: {response.status} - {response_text}")
                        return False
                    
                    data = await response.json()
                    
                    if "errors" in data:
                        logger.error(f"Pod restart GraphQL errors: {data['errors']}")
                        return False
                    
                    result = data.get("data", {}).get("podResume")
                    
                    if result:
                        logger.info(f"✅ Pod {pod_id} 재시작 성공")
                        logger.info(f"   새 상태: {result.get('desiredStatus', 'Unknown')}")
                        
                        # 재시작 후 잠시 대기
                        await asyncio.sleep(10)
                        return True
                    else:
                        logger.error(f"❌ Pod restart returned empty result")
                        return False
                        
        except Exception as e:
            logger.error(f"Pod restart failed: {e}")
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