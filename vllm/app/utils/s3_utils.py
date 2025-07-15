import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

class S3Manager:
    """S3 파일 업로드 관리 클래스"""
    
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region_name: str = "ap-northeast-2",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        self.bucket_name = bucket_name or os.getenv("AWS_S3_BUCKET_NAME")
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-northeast-2")
        
        # AWS 자격 증명 설정
        if aws_access_key_id and aws_secret_access_key:
            self.s3_client = boto3.client(
                's3',
                region_name=self.region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key
            )
        else:
            # 환경 변수 또는 IAM 역할 사용
            self.s3_client = boto3.client('s3', region_name=self.region_name)
        
        self._validate_connection()
    
    def _validate_connection(self):
        """S3 연결 검증"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ S3 버킷 연결 성공: {self.bucket_name}")
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
    
    def upload_file(
        self,
        file_path: str,
        object_name: Optional[str] = None,
        folder_prefix: str = "zonos-tts",
        metadata: Optional[Dict[str, str]] = None,
        public_read: bool = False
    ) -> Dict[str, Any]:
        """
        파일을 S3에 업로드
        
        Args:
            file_path: 업로드할 로컬 파일 경로
            object_name: S3 객체 이름 (None이면 파일명 사용)
            folder_prefix: S3 폴더 prefix
            metadata: 파일 메타데이터
            public_read: public-read 권한 부여 여부
        
        Returns:
            업로드 결과 정보
        """
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
            
            # Public read 권한 설정
            if public_read:
                extra_args['ACL'] = 'public-read'
            
            # 파일 업로드
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                object_name,
                ExtraArgs=extra_args if extra_args else None
            )
            
            # URL 생성
            if public_read:
                url = f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{object_name}"
            else:
                url = self.generate_presigned_url(object_name)
            
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
    
    def generate_presigned_url(
        self,
        object_name: str,
        expiration: int = 3600
    ) -> str:
        """
        S3 객체에 대한 사전 서명된 URL 생성
        
        Args:
            object_name: S3 객체 이름
            expiration: URL 만료 시간 (초)
        
        Returns:
            사전 서명된 URL
        """
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"❌ Presigned URL 생성 실패: {e}")
            raise
    
    def delete_file(self, object_name: str) -> bool:
        """S3에서 파일 삭제"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            logger.info(f"✅ S3 파일 삭제 성공: {object_name}")
            return True
        except ClientError as e:
            logger.error(f"❌ S3 파일 삭제 실패: {e}")
            return False
    
    def file_exists(self, object_name: str) -> bool:
        """S3에 파일 존재 여부 확인"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError:
            return False

# 전역 S3 매니저 인스턴스
_s3_manager: Optional[S3Manager] = None

def get_s3_manager() -> S3Manager:
    """S3 매니저 인스턴스 반환"""
    global _s3_manager
    if _s3_manager is None:
        _s3_manager = S3Manager()
    return _s3_manager

def initialize_s3_manager(
    bucket_name: Optional[str] = None,
    region_name: str = "ap-northeast-2",
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None
) -> S3Manager:
    """S3 매니저 초기화"""
    global _s3_manager
    _s3_manager = S3Manager(
        bucket_name=bucket_name,
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    return _s3_manager