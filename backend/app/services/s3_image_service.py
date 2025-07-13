import boto3
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import uuid
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)


class S3ImageService:
    """S3 이미지 업로드 서비스"""

    def __init__(self):
        self.s3_client = None
        self.bucket_name = settings.S3_BUCKET_NAME
        self.region = settings.AWS_REGION
        
        # S3 클라이언트 초기화
        if settings.S3_ENABLED and settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_REGION
                )
                logger.info(f"S3 클라이언트 초기화 성공: {self.bucket_name}")
            except Exception as e:
                logger.error(f"S3 클라이언트 초기화 실패: {e}")
                self.s3_client = None
        else:
            logger.warning("S3 설정이 완료되지 않았습니다.")

    def is_available(self) -> bool:
        """S3 서비스 사용 가능 여부 확인"""
        if self.s3_client is None:
            return False
        
        # 실제 연결 테스트
        try:
            self.s3_client.list_buckets()
            return True
        except Exception as e:
            logger.warning(f"S3 연결 테스트 실패: {e}")
            return False

    async def upload_image(self, image_data: bytes, filename: str, user_id: str = None) -> str:
        """이미지를 S3에 업로드하고 URL 반환"""
        if not self.is_available():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="S3 서비스를 사용할 수 없습니다."
            )

        try:
            # 파일 확장자 추출
            file_extension = Path(filename).suffix.lower()
            if not file_extension:
                file_extension = '.png'  # 기본값

            # 고유한 파일명 생성
            file_id = str(uuid.uuid4())
            new_filename = f"{file_id}{file_extension}"

            # S3 키 생성 (연도/월/사용자ID/파일명)
            now = datetime.now()
            s3_key = f"images/{now.year}/{now.month:02d}"
            if user_id:
                s3_key += f"/{user_id}"
            s3_key += f"/{new_filename}"

            # S3에 업로드
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=image_data,
                ContentType=self._get_content_type(file_extension),
                ACL='public-read'  # 공개 읽기 권한
            )

            # S3 URL 생성
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            logger.info(f"이미지 S3 업로드 성공: {s3_key} -> {s3_url}")
            return s3_url

        except Exception as e:
            logger.error(f"S3 이미지 업로드 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"S3 이미지 업로드에 실패했습니다: {str(e)}"
            )

    async def upload_local_image_to_s3(self, local_image_path: str, user_id: str = None) -> str:
        """로컬 이미지 파일을 S3에 업로드"""
        if not self.is_available():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="S3 서비스를 사용할 수 없습니다."
            )

        try:
            # 파일 읽기
            with open(local_image_path, 'rb') as f:
                image_data = f.read()

            # 파일명 추출
            filename = Path(local_image_path).name

            # S3에 업로드
            return await self.upload_image(image_data, filename, user_id)

        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"이미지 파일을 찾을 수 없습니다: {local_image_path}"
            )
        except Exception as e:
            logger.error(f"로컬 이미지 S3 업로드 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"로컬 이미지 S3 업로드에 실패했습니다: {str(e)}"
            )

    def _get_content_type(self, file_extension: str) -> str:
        """파일 확장자에 따른 Content-Type 반환"""
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return content_types.get(file_extension.lower(), 'image/jpeg')

    async def delete_image(self, s3_url: str) -> bool:
        """S3에서 이미지 삭제"""
        if not self.is_available():
            return False

        try:
            # URL에서 S3 키 추출
            s3_key = s3_url.replace(f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/", "")
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            logger.info(f"S3 이미지 삭제 성공: {s3_key}")
            return True

        except Exception as e:
            logger.error(f"S3 이미지 삭제 실패: {e}")
            return False

    async def get_image_info(self, s3_url: str) -> Optional[Dict[str, Any]]:
        """S3 이미지 정보 조회"""
        if not self.is_available():
            return None

        try:
            # URL에서 S3 키 추출
            s3_key = s3_url.replace(f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/", "")
            
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return {
                "size": response.get('ContentLength'),
                "content_type": response.get('ContentType'),
                "last_modified": response.get('LastModified'),
                "etag": response.get('ETag')
            }

        except Exception as e:
            logger.error(f"S3 이미지 정보 조회 실패: {e}")
            return None


# 싱글톤 인스턴스
s3_image_service = S3ImageService()


def get_s3_image_service() -> S3ImageService:
    """S3 이미지 서비스 인스턴스 반환"""
    return s3_image_service 