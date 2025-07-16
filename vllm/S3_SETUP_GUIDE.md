# S3 설정 가이드

S3 업로드를 사용하려면 다음 설정이 필요합니다:

## 1. 환경 변수 설정

다음 환경 변수를 설정해야 합니다:

```bash
export S3_BUCKET_NAME="your-bucket-name"         # 또는 AWS_S3_BUCKET_NAME
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_REGION="ap-northeast-2"  # 기본값
```

## 2. API를 통한 설정

또는 `/zonos/configure_s3` 엔드포인트를 사용하여 설정할 수 있습니다:

```bash
curl -X POST http://localhost:8000/zonos/configure_s3 \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "your-bucket-name",
    "region_name": "ap-northeast-2",
    "aws_access_key_id": "your-access-key-id",
    "aws_secret_access_key": "your-secret-access-key"
  }'
```

## 3. S3 업로드 비활성화

S3를 사용하지 않으려면 요청에서 `upload_to_s3`를 `false`로 설정하세요:

```json
{
  "text": "안녕하세요",
  "language": "ko",
  "upload_to_s3": false
}
```

## 문제 해결

### ACL 오류
최신 S3 버킷은 보안을 위해 ACL을 비활성화하는 경우가 많습니다. 
이 경우 `public_read` 옵션은 무시되며, 모든 파일은 presigned URL을 통해 접근 가능합니다.

### S3 미설정 오류
S3 설정이 되어있지 않으면 업로드 시 오류가 발생합니다.
로컬 파일은 정상적으로 생성되며 `/tmp/zonos_tts/` 디렉토리에 저장됩니다.