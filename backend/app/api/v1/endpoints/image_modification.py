"""
이미지 수정 API 엔드포인트
단순 텍스트 설명을 통한 이미지 수정 기능
"""

import uuid
import logging
import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import io
from PIL import Image
from pathlib import Path

from app.database import get_async_db
from app.core.security import get_current_user
from app.services.s3_service import get_s3_service
from app.services.generated_image_service import get_generated_image_service
from app.services.prompt_optimization_service import get_prompt_optimization_service
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

class ImageModificationService:
    """이미지 수정 서비스"""
    
    def __init__(self):
        self.workflow_path = Path(__file__).parent.parent.parent.parent.parent / "workflows" / "image_modify_text_simple.json"
        self.base_workflow = None
        self._load_workflow()
    
    def _load_workflow(self):
        """이미지 수정 워크플로우 로드"""
        try:
            if self.workflow_path.exists():
                with open(self.workflow_path, 'r', encoding='utf-8') as f:
                    self.base_workflow = json.load(f)
                logger.info(f"✅ 이미지 수정 워크플로우 로드 완료: {self.workflow_path}")
            else:
                logger.error(f"❌ 워크플로우 파일을 찾을 수 없음: {self.workflow_path}")
                raise Exception(f"필수 워크플로우 파일이 없습니다: {self.workflow_path}")
        except Exception as e:
            logger.error(f"❌ 워크플로우 로드 실패: {e}")
            raise Exception(f"이미지 수정 워크플로우 초기화 실패: {e}")
    
    async def upload_image_to_comfyui(
        self, 
        image_data: bytes, 
        filename: str, 
        comfyui_endpoint: str,
        folder_type: str = "input"
    ) -> Dict[str, Any]:
        """이미지를 ComfyUI에 업로드"""
        try:
            # 이미지 파일 준비
            files = {
                'image': (filename, io.BytesIO(image_data), 'image/png')
            }
            data = {
                'type': folder_type,
                'overwrite': 'true'
            }
            
            # ComfyUI 업로드 엔드포인트
            upload_url = f"{comfyui_endpoint.rstrip('/')}/upload/image"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(upload_url, files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ ComfyUI에 이미지 업로드 성공: {filename}")
                    return result
                else:
                    logger.error(f"❌ ComfyUI 이미지 업로드 실패: {response.status_code} - {response.text}")
                    raise Exception(f"ComfyUI 이미지 업로드 실패: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"❌ ComfyUI 이미지 업로드 중 오류: {e}")
            raise
    
    def inject_modification_params(
        self, 
        workflow: Dict[str, Any], 
        uploaded_filename: str,
        edit_instruction: str
    ) -> Dict[str, Any]:
        """워크플로우에 수정 파라미터 주입"""
        try:
            # DiptychCreate 노드 (ID: 1)에 업로드된 이미지 파일명 설정
            if "1" in workflow:
                workflow["1"]["inputs"]["image"] = uploaded_filename
                logger.info(f"✅ DiptychCreate 노드에 이미지 설정: {uploaded_filename}")
            
            # InContextEditInstruction 노드 (ID: 9)에 수정 지시사항 설정
            if "9" in workflow:
                workflow["9"]["inputs"]["editText"] = edit_instruction
                logger.info(f"✅ 수정 지시사항 설정: {edit_instruction}")
            
            return workflow
            
        except Exception as e:
            logger.error(f"❌ 워크플로우 파라미터 주입 실패: {e}")
            raise
    
    async def execute_modification_workflow(
        self,
        comfyui_endpoint: str,
        workflow: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """수정 워크플로우 실행"""
        try:
            # API 형식으로 변환
            api_request = {
                "prompt": workflow,
                "client_id": str(uuid.uuid4())
            }
            
            prompt_url = f"{comfyui_endpoint.rstrip('/')}/prompt"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(prompt_url, json=api_request)
                
                if response.status_code == 200:
                    result = response.json()
                    prompt_id = result.get("prompt_id")
                    logger.info(f"✅ 워크플로우 실행 시작: {prompt_id}")
                    
                    # 결과 대기 및 획득
                    return await self._wait_for_result(comfyui_endpoint, prompt_id)
                else:
                    logger.error(f"❌ 워크플로우 실행 실패: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ 워크플로우 실행 중 오류: {e}")
            return None
    
    async def _wait_for_result(
        self,
        comfyui_endpoint: str,
        prompt_id: str,
        max_wait_time: int = 300
    ) -> Optional[Dict[str, Any]]:
        """워크플로우 실행 결과 대기"""
        import asyncio
        
        history_url = f"{comfyui_endpoint.rstrip('/')}/history/{prompt_id}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(max_wait_time // 5):
                await asyncio.sleep(5)
                
                try:
                    response = await client.get(history_url)
                    
                    if response.status_code == 200:
                        history = response.json()
                        
                        if prompt_id in history:
                            execution = history[prompt_id]
                            
                            if "outputs" in execution:
                                logger.info(f"✅ 워크플로우 실행 완료: {prompt_id}")
                                return self._extract_result_image(execution)
                                
                except Exception as e:
                    logger.warning(f"⚠️ 결과 확인 중 오류: {e}")
                    continue
        
        logger.error(f"❌ 워크플로우 실행 타임아웃: {prompt_id}")
        return None
    
    def _extract_result_image(self, execution: Dict[str, Any]) -> Dict[str, Any]:
        """실행 결과에서 수정된 이미지 정보 추출"""
        try:
            outputs = execution.get("outputs", {})
            
            # 디버깅을 위해 모든 출력 노드 로깅
            logger.info(f"📊 워크플로우 실행 결과 - 출력 노드들: {list(outputs.keys())}")
            for node_id, node_output in outputs.items():
                logger.info(f"  노드 {node_id}: {list(node_output.keys()) if isinstance(node_output, dict) else type(node_output)}")
                if isinstance(node_output, dict) and "images" in node_output:
                    logger.info(f"    -> 이미지 발견! 개수: {len(node_output.get('images', []))}")
            
            # SaveImage 노드를 우선적으로 찾기 (일반적으로 최종 출력)
            save_image_nodes = []
            for node_id, node_output in outputs.items():
                if isinstance(node_output, dict) and "images" in node_output:
                    save_image_nodes.append(node_id)
            
            logger.info(f"🖼️ 이미지를 포함한 노드들: {save_image_nodes}")
            
            # 우선순위: SaveImage (39) > ImageCrop (19) > PreviewImage (18) > 기타
            priority_nodes = ["39", "19", "18"] + [n for n in save_image_nodes if n not in ["39", "19", "18"]]
            
            for node_id in priority_nodes:
                if node_id in outputs and "images" in outputs[node_id]:
                    images = outputs[node_id]["images"]
                    if images and len(images) > 0:
                        image_info = images[0]
                        logger.info(f"✅ 노드 {node_id}에서 이미지 정보 추출 성공")
                        return {
                            "filename": image_info.get("filename"),
                            "subfolder": image_info.get("subfolder", ""),
                            "type": image_info.get("type", "output"),
                            "format": image_info.get("format", "png")
                        }
            
            logger.error("❌ 결과에서 이미지 정보를 찾을 수 없음")
            logger.error(f"❌ 전체 outputs 구조: {json.dumps(outputs, indent=2, default=str)[:1000]}...")
            return None
            
        except Exception as e:
            logger.error(f"❌ 이미지 정보 추출 실패: {e}")
            return None
    
    async def download_result_image(
        self,
        comfyui_endpoint: str,
        image_info: Dict[str, Any]
    ) -> Optional[bytes]:
        """결과 이미지 다운로드"""
        try:
            filename = image_info.get("filename")
            subfolder = image_info.get("subfolder", "")
            image_type = image_info.get("type", "output")
            
            view_url = f"{comfyui_endpoint.rstrip('/')}/view"
            params = {
                "filename": filename,
                "type": image_type,
                "subfolder": subfolder
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(view_url, params=params)
                
                if response.status_code == 200:
                    logger.info(f"✅ 이미지 다운로드 성공: {filename}")
                    return response.content
                else:
                    logger.error(f"❌ 이미지 다운로드 실패: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ 이미지 다운로드 중 오류: {e}")
            return None

# 서비스 인스턴스
image_modification_service = ImageModificationService()

@router.post("/modify-simple")
async def modify_image_simple(
    image: UploadFile = File(..., description="수정할 이미지 파일"),
    edit_instruction: str = Form(..., description="이미지 수정 지시사항 (예: Make her hair blue)"),
    workflow_id: str = Form(default="image_modify_text_simple", description="사용할 워크플로우 ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user),
):
    """
    단순 텍스트 설명으로 이미지 수정
    
    - **image**: 수정할 이미지 파일
    - **edit_instruction**: 수정 지시사항 (예: "Make her hair blue", "Change background to sunset")
    - **workflow_id**: 사용할 워크플로우 ID (기본값: image_modify_text_simple)
    """
    try:
        # 사용자 정보 추출
        user_id = current_user["sub"]
        
        # 사용자의 팀 정보 확인
        teams = current_user.get("teams", [])
        if not teams:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="소속된 팀이 없습니다"
            )
        
        # 첫 번째 팀의 ID 사용 (팀 정보는 문자열로 저장되어 있음)
        team_id = 1  # 기본값으로 설정, 실제로는 JWT에서 추출해야 함
        
        # 이미지 파일 읽기
        image_data = await image.read()
        
        # 이미지 검증
        try:
            img = Image.open(io.BytesIO(image_data))
            img.verify()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 이미지 파일입니다"
            )
        
        # 사용자 세션에서 ComfyUI 엔드포인트 가져오기
        from app.services.user_session_service import get_user_session_service
        from app.services.runpod_service import get_runpod_service
        
        user_session_service = get_user_session_service()
        session_status = await user_session_service.get_session_status(user_id, db)
        
        if not session_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="활성 세션이 없습니다. 먼저 이미지 생성 세션을 시작해주세요."
            )
        
        pod_id = session_status.get("pod_id")
        if not pod_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pod ID를 찾을 수 없습니다. 세션을 다시 시작해주세요."
            )
        
        # RunPod에서 ComfyUI 엔드포인트 가져오기
        runpod_service = get_runpod_service()
        pod_info = await runpod_service.get_pod_status(pod_id)
        
        if not pod_info or not pod_info.endpoint_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ComfyUI 엔드포인트를 찾을 수 없습니다"
            )
        
        comfyui_endpoint = pod_info.endpoint_url
        logger.info(f"🚀 이미지 수정 ComfyUI 엔드포인트: {comfyui_endpoint}")
        
        # 세션을 이미지 수정 작업으로 표시
        await user_session_service.start_image_generation(user_id, db)
        
        # 프롬프트 최적화
        optimized_instruction = edit_instruction
        try:
            prompt_service = get_prompt_optimization_service()
            optimized_instruction = await prompt_service.optimize_image_modification_prompt(edit_instruction)
            logger.info(f"✅ 프롬프트 최적화 완료: {edit_instruction} -> {optimized_instruction}")
        except Exception as e:
            logger.warning(f"프롬프트 최적화 실패, 원본 사용: {e}")
            optimized_instruction = edit_instruction
        
        # 1. ComfyUI에 이미지 업로드
        upload_filename = f"modify_{user_id}_{uuid.uuid4().hex}.png"
        upload_result = await image_modification_service.upload_image_to_comfyui(
            image_data=image_data,
            filename=upload_filename,
            comfyui_endpoint=comfyui_endpoint
        )
        
        logger.info(f"ComfyUI 업로드 결과: {upload_result}")
        
        # 2. 워크플로우에 파라미터 주입 (최적화된 프롬프트 사용)
        workflow = image_modification_service.base_workflow.copy()
        workflow = image_modification_service.inject_modification_params(
            workflow=workflow,
            uploaded_filename=upload_filename,
            edit_instruction=optimized_instruction
        )
        
        # 3. 워크플로우 실행
        result = await image_modification_service.execute_modification_workflow(
            comfyui_endpoint=comfyui_endpoint,
            workflow=workflow
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="이미지 수정 처리 실패"
            )
        
        # 4. 결과 이미지 다운로드
        result_image_data = await image_modification_service.download_result_image(
            comfyui_endpoint=comfyui_endpoint,
            image_info=result
        )
        
        if not result_image_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="수정된 이미지 다운로드 실패"
            )
        
        # 5. S3에 저장
        s3_service = get_s3_service()
        storage_id = str(uuid.uuid4())
        s3_key = f"modified_images/team_{team_id}/{user_id}/{storage_id}.png"
        
        s3_url = await s3_service.upload_image_data(
            image_data=result_image_data,
            key=s3_key,
            content_type="image/png",
            return_presigned=True
        )
        
        if not s3_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="S3 업로드 실패"
            )
        
        # 6. DB에 저장
        generated_image_service = get_generated_image_service()
        await generated_image_service.save_generated_image(
            db=db,
            storage_id=storage_id,
            team_id=team_id,
            user_id=user_id,
            prompt=f"[Modified] {edit_instruction}",
            negative_prompt="",
            width=img.width,
            height=img.height,
            seed=None,
            workflow_name=workflow_id,
            model_name="FLUX.1-dev",
            extra_metadata={
                "original_image": image.filename,
                "edit_instruction": edit_instruction,
                "optimized_instruction": optimized_instruction,
                "modification_type": "simple_text"
            },
            file_size=len(result_image_data)
        )
        
        # 세션 완료 처리 (10분 연장)
        await user_session_service.complete_image_generation(user_id, db)
        
        return {
            "success": True,
            "message": "이미지 수정 완료",
            "storage_id": storage_id,
            "s3_url": s3_url,
            "width": img.width,
            "height": img.height,
            "edit_instruction": edit_instruction
        }
        
    except HTTPException:
        # HTTPException의 경우에도 세션 상태 리셋
        try:
            await user_session_service.complete_image_generation(user_id, db)
        except:
            pass
        raise
    except Exception as e:
        logger.error(f"이미지 수정 중 오류 발생: {e}")
        # 예외 발생시에도 세션 상태 리셋
        try:
            await user_session_service.complete_image_generation(user_id, db)
        except:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이미지 수정 중 오류가 발생했습니다: {str(e)}"
        )