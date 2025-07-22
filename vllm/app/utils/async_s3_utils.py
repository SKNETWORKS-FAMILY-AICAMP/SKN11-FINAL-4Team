import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import aioboto3
from botocore.exceptions import ClientError, NoCredentialsError
import aiofiles
from dotenv import load_dotenv
import asyncio

load_dotenv()

logger = logging.getLogger(__name__)

class AsyncS3Manager:
    """비동기 S3 파일 업로드 관리 클래스"""
    
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region_name: str = "ap-northeast-2",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME")
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-northeast-2")
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        
        # aioboto3 세션 생성
        self.session = aioboto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
    
    async def validate_connection(self):
        """S3 연결 검증"""
        try:
            async with self.session.client('s3') as s3_client:
                await s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"✅ S3 버킷 연결 성공: {self.bucket_name}")
                return True
        except NoCredentialsError:
            logger.error("❌ AWS 자격 증명이 설정되지 않았습니다.")
            raise
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"❌ S3 버킷을 찾을 수 없습니다: {self.bucket_name}")
            else:
                logger.error(f"❌ S3 연결 오류: {e}")
            raise
    
    async def upload_file(
        self,
        file_path: str,
        object_name: Optional[str] = None,
        folder_prefix: str = "zonos-tts",
        metadata: Optional[Dict[str, str]] = None,
        public_read: bool = False
    ) -> Dict[str, Any]:
        """
        파일을 S3에 비동기로 업로드
        
        Args:
            file_path: 업로드할 로컬 파일 경로
            object_name: S3 객체 이름 (None이면 파일명 사용)
            folder_prefix: S3 폴더 prefix
            metadata: 파일 메타데이터
            public_read: public-read 권한 부여 여부
        
        Returns:
            업로드 결과 정보
        """
        # 버킷 이름 검증
        if not self.bucket_name:
            raise ValueError("S3 bucket name is not configured. Please set AWS_S3_BUCKET_NAME environment variable or configure S3.")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        # S3 객체 이름 설정
        if object_name is None:
            object_name = os.path.basename(file_path)
        
        # 폴더 prefix 추가
        if folder_prefix:
            object_name = f"{folder_prefix}/{object_name}"
        
        try:
            # ExtraArgs 설정
            extra_args = {}
            
            # 메타데이터 추가
            if metadata:
                extra_args['Metadata'] = metadata
            
            # Content-Type 설정
            if file_path.endswith('.wav'):
                extra_args['ContentType'] = 'audio/wav'
            elif file_path.endswith('.mp3'):
                extra_args['ContentType'] = 'audio/mpeg'
            
            # Public read 권한 설정 (ACL을 지원하는 버킷만)
            # 최신 S3 버킷은 ACL을 지원하지 않을 수 있음
            # if public_read:
            #     extra_args['ACL'] = 'public-read'
            
            # 비동기 파일 업로드
            async with self.session.client('s3') as s3_client:
                # 파일을 비동기로 읽고 업로드
                async with aiofiles.open(file_path, 'rb') as file:
                    file_data = await file.read()
                    
                await s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=object_name,
                    Body=file_data,
                    **extra_args
                )
                
                # URL 생성 - ACL 없이는 항상 presigned URL 사용
                # if public_read:
                #     url = f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{object_name}"
                # else:
                url = await self.generate_presigned_url(object_name)
            
            logger.info(f"✅ S3 업로드 성공: {object_name}")
            
            return {
                "success": True,
                "bucket": self.bucket_name,
                "key": object_name,
                "url": url,
                "region": self.region_name
            }
            
        except ClientError as e:
            logger.error(f"❌ S3 업로드 실패: {e}")
            raise
    
    async def upload_file_from_bytes(
        self,
        file_data: bytes,
        object_name: str,
        folder_prefix: str = "zonos-tts",
        metadata: Optional[Dict[str, str]] = None,
        public_read: bool = False,
        content_type: str = "audio/wav"
    ) -> Dict[str, Any]:
        """
        바이트 데이터를 S3에 비동기로 업로드
        """
        # 버킷 이름 검증
        if not self.bucket_name:
            raise ValueError("S3 bucket name is not configured. Please set AWS_S3_BUCKET_NAME environment variable or configure S3.")
        # 폴더 prefix 추가
        if folder_prefix:
            object_name = f"{folder_prefix}/{object_name}"
        
        try:
            # ExtraArgs 설정
            extra_args = {
                'ContentType': content_type
            }
            
            # 메타데이터 추가
            if metadata:
                extra_args['Metadata'] = metadata
            
            # Public read 권한 설정 (ACL을 지원하는 버킷만)
            # 최신 S3 버킷은 ACL을 지원하지 않을 수 있음
            # if public_read:
            #     extra_args['ACL'] = 'public-read'
            
            # 비동기 업로드
            async with self.session.client('s3') as s3_client:
                await s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=object_name,
                    Body=file_data,
                    **extra_args
                )
                
                # URL 생성 - ACL 없이는 항상 presigned URL 사용
                # if public_read:
                #     url = f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{object_name}"
                # else:
                url = await self.generate_presigned_url(object_name)
            
            logger.info(f"✅ S3 업로드 성공: {object_name}")
            
            return {
                "success": True,
                "bucket": self.bucket_name,
                "key": object_name,
                "url": url,
                "region": self.region_name
            }
            
        except ClientError as e:
            logger.error(f"❌ S3 업로드 실패: {e}")
            raise
    
    async def generate_presigned_url(
        self,
        object_name: str,
        expiration: int = 3600
    ) -> str:
        """
        S3 객체에 대한 사전 서명된 URL 비동기 생성
        """
        try:
            async with self.session.client('s3') as s3_client:
                response = await s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': object_name},
                    ExpiresIn=expiration
                )
                return response
        except ClientError as e:
            logger.error(f"❌ Presigned URL 생성 실패: {e}")
            raise
    
    async def delete_file(self, object_name: str) -> bool:
        """S3에서 파일 비동기 삭제"""
        try:
            async with self.session.client('s3') as s3_client:
                await s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
                logger.info(f"✅ S3 파일 삭제 성공: {object_name}")
                return True
        except ClientError as e:
            logger.error(f"❌ S3 파일 삭제 실패: {e}")
            return False
    
    async def file_exists(self, object_name: str) -> bool:
        """S3에 파일 존재 여부 비동기 확인"""
        try:
            async with self.session.client('s3') as s3_client:
                await s3_client.head_object(Bucket=self.bucket_name, Key=object_name)
                return True
        except ClientError:
            return False

# 전역 비동기 S3 매니저 인스턴스 (thread-safe)
_async_s3_manager: Optional[AsyncS3Manager] = None
_async_s3_manager_lock = asyncio.Lock()

async def get_async_s3_manager() -> AsyncS3Manager:
    """비동기 S3 매니저 인스턴스 반환 (thread-safe)"""
    global _async_s3_manager
    async with _async_s3_manager_lock:
        if _async_s3_manager is None:
            _async_s3_manager = AsyncS3Manager()
    return _async_s3_manager

async def initialize_async_s3_manager(
    bucket_name: Optional[str] = None,
    region_name: str = "ap-northeast-2",
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None
) -> AsyncS3Manager:
    """비동기 S3 매니저 초기화 (thread-safe)"""
    global _async_s3_manager
    async with _async_s3_manager_lock:
        _async_s3_manager = AsyncS3Manager(
            bucket_name=bucket_name,
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
    return _async_s3_manager