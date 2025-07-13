import boto3
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

def test_aws_credentials():
    """AWS 자격 증명 테스트"""
    try:
        # 환경 변수 확인
        access_key = os.getenv('AWS_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_REGION')
        bucket = os.getenv('S3_BUCKET_NAME')
        
        print(f"Access Key ID: {access_key}")
        print(f"Secret Key: {secret_key[:10]}..." if secret_key else "None")
        print(f"Region: {region}")
        print(f"Bucket: {bucket}")
        
        # S3 클라이언트 생성
        s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
        # 버킷 리스트 조회 (기본 권한 테스트)
        print("\n=== 버킷 리스트 조회 ===")
        response = s3_client.list_buckets()
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        print(f"사용 가능한 버킷: {buckets}")
        
        # 특정 버킷 존재 확인
        if bucket in buckets:
            print(f"✅ 버킷 '{bucket}'이 존재합니다")
        else:
            print(f"❌ 버킷 '{bucket}'이 존재하지 않습니다")
            
        # 버킷 권한 테스트
        try:
            print("\n=== 버킷 권한 테스트 ===")
            response = s3_client.head_bucket(Bucket=bucket)
            print(f"✅ 버킷 '{bucket}'에 접근 권한이 있습니다")
        except Exception as e:
            print(f"❌ 버킷 '{bucket}' 접근 실패: {e}")
            
    except Exception as e:
        print(f"❌ AWS 자격 증명 테스트 실패: {e}")

if __name__ == "__main__":
    test_aws_credentials() 