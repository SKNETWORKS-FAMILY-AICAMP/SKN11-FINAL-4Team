"""
RunPod Serverless 파인튜닝 클라이언트
"""

import os
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class RunPodFineTuningClient:
    """RunPod 파인튜닝 API 클라이언트"""
    
    def __init__(self):
        self.api_key = os.getenv("RUNPOD_API_KEY")
        self.endpoint_id = os.getenv("RUNPOD_FINETUNING_ENDPOINT_ID")
        self.base_url = "https://api.runpod.ai/v2"
        
        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY 환경 변수가 설정되지 않았습니다")
        
        if not self.endpoint_id:
            logger.warning("RUNPOD_FINETUNING_ENDPOINT_ID가 설정되지 않았습니다. 동적으로 찾습니다.")
    
    async def find_or_create_endpoint(self) -> str:
        """파인튜닝 엔드포인트를 찾거나 생성"""
        if self.endpoint_id:
            return self.endpoint_id
        
        # GraphQL로 기존 엔드포인트 찾기
        graphql_url = "https://api.runpod.io/graphql"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 엔드포인트 목록 조회
        query = """
        query {
            myself {
                serverlessDiscount {
                    discountedPrice
                }
                endpoints {
                    id
                    name
                    templateId
                    workersMin
                    workersMax
                    status
                }
            }
        }
        """
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    graphql_url,
                    json={"query": query},
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    endpoints = data.get("data", {}).get("myself", {}).get("endpoints", [])
                    
                    # 파인튜닝 엔드포인트 찾기
                    for endpoint in endpoints:
                        if "finetuning" in endpoint.get("name", "").lower():
                            self.endpoint_id = endpoint["id"]
                            logger.info(f"✅ 기존 파인튜닝 엔드포인트 발견: {self.endpoint_id}")
                            return self.endpoint_id
                
                logger.warning("파인튜닝 엔드포인트를 찾을 수 없습니다")
                
        except Exception as e:
            logger.error(f"엔드포인트 조회 실패: {e}")
        
        # 엔드포인트를 찾지 못한 경우 환경 변수 확인
        if not self.endpoint_id:
            raise ValueError("파인튜닝 엔드포인트를 찾을 수 없습니다. RUNPOD_FINETUNING_ENDPOINT_ID를 설정하세요.")
        
        return self.endpoint_id
    
    async def start_finetuning(
        self,
        task_id: str,
        qa_data: List[Dict[str, Any]],
        system_message: str,
        hf_token: str,
        hf_repo_id: str,
        training_epochs: int,
        influencer_id: str
    ) -> Dict[str, Any]:
        """파인튜닝 작업 시작"""
        
        # 엔드포인트 ID 확인
        endpoint_id = await self.find_or_create_endpoint()
        
        # RunPod API URL
        url = f"{self.base_url}/{endpoint_id}/run"
        
        # 요청 헤더
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 요청 데이터
        payload = {
            "input": {
                "task_id": task_id,
                "qa_data": qa_data,
                "system_message": system_message,
                "hf_token": hf_token,
                "hf_repo_id": hf_repo_id,
                "training_epochs": training_epochs,
                "influencer_id": influencer_id
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    job_id = result.get("id")
                    logger.info(f"✅ 파인튜닝 작업 시작됨: {task_id}, Job ID: {job_id}")
                    return {
                        "success": True,
                        "job_id": job_id,
                        "status": result.get("status", "IN_QUEUE")
                    }
                else:
                    error_msg = f"RunPod API 오류: {response.status_code}, {response.text}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg
                    }
                    
        except Exception as e:
            error_msg = f"파인튜닝 요청 실패: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    async def check_status(self, job_id: str) -> Dict[str, Any]:
        """파인튜닝 작업 상태 확인"""
        
        # 엔드포인트 ID 확인
        endpoint_id = await self.find_or_create_endpoint()
        
        # RunPod API URL
        url = f"{self.base_url}/{endpoint_id}/status/{job_id}"
        
        # 요청 헤더
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "status": result.get("status"),
                        "output": result.get("output"),
                        "error": result.get("error")
                    }
                else:
                    return {
                        "success": False,
                        "error": f"상태 확인 실패: {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"상태 확인 오류: {str(e)}"
            }
    
    async def cancel_job(self, job_id: str) -> bool:
        """파인튜닝 작업 취소"""
        
        # 엔드포인트 ID 확인
        endpoint_id = await self.find_or_create_endpoint()
        
        # RunPod API URL
        url = f"{self.base_url}/{endpoint_id}/cancel/{job_id}"
        
        # 요청 헤더
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    timeout=30.0
                )
                
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"작업 취소 실패: {e}")
            return False